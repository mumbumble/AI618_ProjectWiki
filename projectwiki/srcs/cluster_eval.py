"""Compare clustering methods on one saved Record with disjoint grouping ratings.

No encoder or LLM is called. Validation ratings can select metric_l2; test ratings
are used only for the final report. Ratings 4-5 mean same group, 1-2 mean separate;
the middle range affects distance RMSE but is excluded from group agreement.
"""
from __future__ import annotations

import time
from collections import Counter
from dataclasses import replace
from pathlib import PurePosixPath

import numpy as np

from ..config import Config
from ..models.clustering import get_clusterer, mixed_distance, resolve_ratings
from ..schema import Preferences
from .candidates import reference_candidates
from .record import Record


def pair_keys(pairs: list[dict]) -> set[tuple[str, str]]:
    return {tuple(sorted((p["a"], p["b"]))) for p in pairs}


def distance_rmse(dist: np.ndarray, pairs: list[dict], record: Record) -> float:
    idx = record.file_index
    errors = [dist[idx[p["a"]], idx[p["b"]]] - (5.0 - p["score"]) / 4.0 for p in pairs]
    return float(np.sqrt(np.mean(np.square(errors))))


def grouping_scores(groups, pairs: list[dict]) -> dict:
    group_of = {fid: g.id for g in groups for fid in g.members}
    same, separate, covered = [], [], []
    for p in pairs:
        assigned = p["a"] in group_of and p["b"] in group_of
        together = assigned and group_of[p["a"]] == group_of[p["b"]]
        if p["score"] >= 4:
            same.append(assigned and together)
            covered.append(assigned)
        elif p["score"] <= 2:
            # Leaving both files as noise is an abstention, not a correct separation.
            separate.append(assigned and not together)
            covered.append(assigned)
    same_recall = float(np.mean(same)) if same else None
    separate_recall = float(np.mean(separate)) if separate else None
    return {
        "same_pairs": len(same), "separate_pairs": len(separate),
        "neutral_pairs": len(pairs) - len(same) - len(separate),
        "pair_accuracy": float(np.mean(same + separate)) if same or separate else None,
        "pair_coverage": float(np.mean(covered)) if covered else None,
        "abstained_pairs": len(covered) - sum(covered),
        "covered_pair_accuracy": sum(same + separate) / sum(covered) if any(covered) else None,
        "same_group_recall": same_recall, "separate_group_recall": separate_recall,
        "balanced_accuracy": (same_recall + separate_recall) / 2 if same and separate else None,
    }


def resolve_tasks(record: Record, tasks: list[dict]) -> list[dict]:
    """Tasks are report-only file-finding checklists, never clustering supervision."""
    resolved = []
    for task in tasks:
        if not isinstance(task, dict) or not isinstance(task.get("name"), str) or not task["name"].strip():
            raise ValueError("each onboarding task requires a name")
        refs = task.get("files")
        if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) for ref in refs):
            raise ValueError("each onboarding task requires a nonempty files list")
        ids = list(dict.fromkeys(record.resolve(ref) for ref in refs))
        if None in ids:
            raise ValueError(f"onboarding task refers to a missing file: {task['name']}")
        resolved.append({"name": task["name"], "files": ids})
    return resolved


def task_scores(groups, tasks: list[dict], record: Record) -> list[dict]:
    """Compute project-defined file-finding proxies, not measured user efficiency.

    Related motivation: S. Mancoridis et al. (IWPC 1998), "Using Automatic
    Clustering to Produce High-Level System Organizations of Source Code".
    https://doi.org/10.1109/WPC.1998.693283

    That work motivates software-structure recovery through clustering. It does
    not establish our checklists or these metrics as validated onboarding measures.
    Counting target groups/ungrouped files as visits and scanning every file in a
    visited group are our explicit assumptions; a user study is still required.
    """
    group_of = {fid: g.id for g in groups for fid in g.members}
    sizes = {g.id: len(g.members) for g in groups}
    results = []
    for task in tasks:
        visited = {group_of[fid] for fid in task["files"] if fid in group_of}
        ungrouped = sum(fid not in group_of for fid in task["files"])
        scanned = sum(sizes[gid] for gid in visited) + ungrouped
        results.append({"name": task["name"], "files": [record.file_by_id[fid].path for fid in task["files"]],
                        "groups_to_visit": len(visited) + ungrouped, "files_to_scan": scanned,
                        "extra_files": scanned - len(task["files"]), "ungrouped_targets": ungrouped})
    return results


def describe_groups(groups, record: Record) -> list[dict]:
    descriptions = []
    for group in groups:
        if not group.members:
            continue
        rows = [record.file_index[fid] for fid in group.members]
        vectors = record.file_emb[rows]
        central = int(np.argmax(vectors @ vectors.mean(0)))
        file = record.file_by_id[group.members[central]]
        # Markdown's first chunk can be just '# Method'; prefer an actual body excerpt.
        chunk = max((c for c in record.file_chunks(file.id) if c.kind != "path"),
                    key=lambda c: len(c.text.strip()), default=None)
        descriptions.append({"id": group.id, "members": [record.file_by_id[fid].path for fid in group.members],
                             "representative": file.path, "preview": chunk.text[:220] if chunk else "",
                             "locator": chunk.locator if chunk else "path only",
                             "types": dict(Counter(record.file_by_id[fid].type for fid in group.members)),
                             "folders": sorted({str(PurePosixPath(record.file_by_id[fid].path).parent)
                                                for fid in group.members})})
    return descriptions


def pair_outcomes(groups, pairs: list[dict], record: Record) -> list[dict]:
    group_of = {fid: g.id for g in groups for fid in g.members}
    rows = []
    for pair in pairs:
        assigned = pair["a"] in group_of and pair["b"] in group_of
        together = assigned and group_of[pair["a"]] == group_of[pair["b"]]
        expected = "same" if pair["score"] >= 4 else "separate" if pair["score"] <= 2 else "neutral"
        predicted = ("same" if together else "separate") if assigned else "abstained"
        rows.append({"a": record.file_by_id[pair["a"]].path, "b": record.file_by_id[pair["b"]].path,
                     "score": pair["score"], "expected": expected, "predicted": predicted,
                     "correct": expected == predicted if expected != "neutral" else None})
    return rows


def compare_clusterers(record: Record, prefs: Preferences, test_pairs: list, cfg: Config,
                       validation_pairs: list | None = None, l2_grid: list[float] | None = None,
                       methods: list[str] | None = None, tasks: list[dict] | None = None) -> dict:
    """Fit on prefs.pairs only; reject any pair shared by train, validation or test."""
    train, train_stats = resolve_ratings(record, prefs.pairs)
    test, test_stats = resolve_ratings(record, test_pairs)
    validation, validation_stats = resolve_ratings(record, validation_pairs or [])
    if not test:
        raise ValueError("test ratings must contain at least one valid file pair")
    if validation_pairs is not None and not validation:
        raise ValueError("validation ratings must contain at least one valid file pair")
    if l2_grid is not None and validation_pairs is None:
        raise ValueError("an l2 grid requires separate validation ratings")
    method_names = list(dict.fromkeys(methods if methods is not None else ("baseline", "pref", "metric")))
    if not method_names:
        raise ValueError("select at least one clustering method")
    if validation_pairs is not None and "metric" not in method_names:
        raise ValueError("metric_l2 selection requires the metric method")
    splits = {"train": pair_keys(train), "validation": pair_keys(validation), "test": pair_keys(test)}
    for a, b in (("train", "validation"), ("train", "test"), ("validation", "test")):
        if splits[a] & splits[b]:
            raise ValueError(f"{a} and {b} ratings overlap (including reversed paths/file IDs)")
    clean_prefs = replace(prefs, pairs=train)
    resolved_tasks = resolve_tasks(record, tasks or [])
    structural = {tuple(sorted((a, b))) for a, b, reason, _, _ in reference_candidates(record)
                  if reason in ("imports", "links_to")}
    metric_cfg = cfg
    selection = None
    if validation_pairs is not None:
        grid = sorted(set(l2_grid if l2_grid is not None else [0.01, 0.1, 1.0]))
        if not grid or any(not np.isfinite(v) or v <= 0 for v in grid):
            raise ValueError("l2 grid values must be finite and positive")
        trials = []
        for l2 in grid:
            model = get_clusterer("metric", replace(cfg, metric_l2=l2))
            dist = model.distance_matrix(record, clean_prefs)
            trials.append({"metric_l2": float(l2), "validation_rmse": distance_rmse(dist, validation, record)})
        best = min(trials, key=lambda t: (t["validation_rmse"], t["metric_l2"]))
        metric_cfg = replace(cfg, metric_l2=best["metric_l2"])
        selection = {"trials": trials, "selected_l2": best["metric_l2"],
                     "criterion": "validation_distance_rmse"}

    results = {}
    for name in method_names:
        model = get_clusterer(name, metric_cfg if name == "metric" else cfg)
        start = time.perf_counter()
        groups = model.cluster(record, clean_prefs)
        seconds = time.perf_counter() - start
        dist = getattr(model, "distances_", None)
        if name == "baseline":
            dist = mixed_distance(record, cfg.cluster_alpha)
        elif dist is None and hasattr(model, "distance_matrix"):
            dist = model.distance_matrix(record, clean_prefs)
        assigned = {fid for g in groups for fid in g.members}
        if len(assigned) != sum(len(g.members) for g in groups):
            raise ValueError(f"{name}: files must not occur in multiple groups")
        group_of = {fid: g.id for g in groups for fid in g.members}
        within_refs = sum(a in group_of and b in group_of and group_of[a] == group_of[b] for a, b in structural)
        task_results = task_scores(groups, resolved_tasks, record)
        results[name] = {
            "distance_rmse": distance_rmse(dist, test, record) if dist is not None else None,
            **grouping_scores(groups, test),
            "training_agreement": grouping_scores(groups, train),
            "group_count": sum(bool(g.members) for g in groups),
            "group_sizes": [len(g.members) for g in groups if g.members],
            "ungrouped": len(record.files) - len(assigned), "seconds": round(seconds, 6),
            "file_coverage": len(assigned) / len(record.files) if record.files else None,
            "singleton_groups": sum(len(g.members) == 1 for g in groups),
            "structural_cohesion": within_refs / len(structural) if structural else None,
            "structural_pairs": len(structural), "structural_within_groups": within_refs,
            "task_scores": task_results,
            "mean_groups_to_visit": float(np.mean([t["groups_to_visit"] for t in task_results])) if task_results else None,
            "mean_files_to_scan": float(np.mean([t["files_to_scan"] for t in task_results])) if task_results else None,
            "groups": describe_groups(groups, record),
            "ungrouped_files": [f.path for f in record.files if f.id not in assigned],
            "pair_outcomes": pair_outcomes(groups, test, record),
            "diagnostics": getattr(model, "diagnostics", None),
        }
    return {
        "rating_meaning": "same_group_preference", "root": record.root, "encoder": record.encoder_id,
        "files": len(record.files),
        "settings": {"cluster_alpha": cfg.cluster_alpha, "cluster_pct": cfg.cluster_pct,
                     "metric_l2": metric_cfg.metric_l2, "metric_use_type": cfg.metric_use_type,
                     "graph_neighbors": cfg.graph_neighbors, "graph_max_clusters": cfg.graph_max_clusters,
                     "graph_reference_weight": cfg.graph_reference_weight, "cluster_seed": cfg.cluster_seed,
                     "hdbscan_min_cluster_size": cfg.hdbscan_min_cluster_size,
                     "hdbscan_min_samples": cfg.hdbscan_min_samples,
                     "guide": prefs.guide, "anchors": prefs.anchors, "purpose": prefs.purpose},
        "splits": {"train": train_stats, "validation": validation_stats, "test": test_stats},
        "ratings": {"train": train, "validation": validation, "test": test},
        "onboarding_tasks": resolved_tasks,
        "selection": selection, "methods": results,
    }


def parameter_sensitivity(record: Record, prefs: Preferences, test_pairs: list, cfg: Config,
                          tasks: list[dict] | None = None) -> list[dict]:
    """Predeclared exploratory grid; report all results without selecting a winner."""
    experiments = [("constrained", "cluster_pct", [25.0, 35.0, 45.0]),
                   ("graph", "graph_neighbors", [2, 3, 4]),
                   ("hdbscan", "hdbscan_min_cluster_size", [2, 3, 4])]
    rows = []
    for method, field, values in experiments:
        for value in values:
            run = compare_clusterers(record, prefs, test_pairs, replace(cfg, **{field: value}),
                                     methods=[method], tasks=tasks)["methods"][method]
            rows.append({"method": method, "parameter": field, "value": value,
                         "main_setting": value == getattr(cfg, field),
                         **{key: run[key] for key in ("pair_accuracy", "balanced_accuracy", "file_coverage",
                                                      "pair_coverage", "group_count", "ungrouped",
                                                      "mean_groups_to_visit", "mean_files_to_scan")}})
    return rows
