"""Deeper analysis of the benchmark results. No model calls.

    python benchmark/eval/analyze.py   # after run_eval.py; -> runs/bench/results/ANALYSIS.md

1. recall by file-type pair (code-code, doc-code, paper-code, paper-paper/doc, ...)
2. paired bootstrap over projects: confidence intervals for differences between systems
3. ground-truth completeness of the real projects, estimated from the random pairs in the labeling pool
4. hard negatives of the mock projects: how often each system links the designed decoys
5. relation-type confusions on matched pairs
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

EVAL = Path(__file__).resolve().parent
ROOT = EVAL.parents[1]
HERE = ROOT / "benchmark"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(EVAL))

from projectwiki.schema import Graph  # noqa: E402
from graph_metrics import evaluate, predicted  # noqa: E402
from gt_format import GroundTruth, category, pair_key  # noqa: E402

RUNS = ROOT / "runs"
SYSTEMS = {"pipeline": ("bench", "final_graph.json"), "no-LLM": ("bench_nollm", "final_graph.json"),
           "LLM-only": ("bench", "llm_only_graph.json")}
CODEISH = {"code", "notebook", "config"}


def pair_type(a: str, b: str) -> str:
    ca, cb = category(a), category(b)
    if "image" in (ca, cb):
        return "figure-*"
    sides = {("code" if c in CODEISH else c) for c in (ca, cb)}
    if sides == {"code"}:
        return "code-code"
    if sides == {"doc", "code"}:
        return "doc-code"
    if sides == {"paper", "code"}:
        return "paper-code"
    if sides <= {"paper", "doc"}:
        return "paper/doc-paper/doc"
    return "other"


def load(name: str):
    gt = GroundTruth.load(HERE / "gt" / name / "gt.json")
    graphs = {}
    for s, (run, file) in SYSTEMS.items():
        p = RUNS / run / name / file
        if p.exists():
            graphs[s] = Graph.from_dict(json.loads(p.read_text(encoding="utf-8")))
    return gt, graphs


def names() -> tuple[list[str], list[str]]:
    real = sorted(p.parent.name for p in (HERE / "gt").glob("*/gt.json") if not p.parent.name.startswith("mock_"))
    mock = sorted(p.parent.name for p in (HERE / "gt").glob("mock_*/gt.json") if (RUNS / "bench" / p.parent.name / "graph.json").exists())
    return real, mock


def recall_by_type(group: list[str]) -> dict:
    found = defaultdict(lambda: defaultdict(int))
    total = defaultdict(int)
    for n in group:
        gt, graphs = load(n)
        req = [e for e in gt.edges if e.required]
        for e in req:
            total[pair_type(e.a, e.b)] += 1
        for s, g in graphs.items():
            pred = predicted(g)
            for e in req:
                found[s][pair_type(e.a, e.b)] += e.key in pred
    return {"total": dict(total), "recall": {s: {t: found[s][t] / total[t] for t in total} for s in found}}


def bootstrap(scores: dict, group: list[str], metric: str, a: str, b: str, iters: int = 10000, seed: int = 0) -> dict:
    """Paired bootstrap over projects of mean(metric_a - metric_b)."""
    diffs = [scores[a][n][metric] - scores[b][n][metric] for n in group
             if n in scores[a] and n in scores[b] and None not in (scores[a][n][metric], scores[b][n][metric])]
    if not diffs:
        return {}
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(diffs) for _ in diffs) / len(diffs) for _ in range(iters))
    return {"mean": sum(diffs) / len(diffs), "lo": means[int(0.025 * iters)], "hi": means[int(0.975 * iters)],
            "n": len(diffs), "wins": sum(d > 0 for d in diffs), "losses": sum(d < 0 for d in diffs)}


def completeness(group: list[str]) -> dict:
    """Relations among pairs no pooled system proposed, estimated from the random pairs' labels."""
    pool_path, lab_path = RUNS / "bench" / "_gt" / "pool.json", RUNS / "bench" / "_gt" / "claude_labels.json"
    if not pool_path.exists() or not lab_path.exists():
        return {}
    pool, labels = json.loads(pool_path.read_text(encoding="utf-8")), json.loads(lab_path.read_text(encoding="utf-8"))
    out = {}
    for n in group:
        if n not in pool:
            continue
        gt = GroundTruth.load(HERE / "gt" / n / "gt.json")
        paths = sorted({p for e in gt.edges for p in (e.a, e.b)} | {p for x in gt.negatives for p in (x["a"], x["b"])}
                       | {p for it in pool[n]["items"] for p in (it["a"], it["b"])})
        record_files = json.loads((RUNS / "bench" / n / "record" / "files.json").read_text(encoding="utf-8")) \
            if (RUNS / "bench" / n / "record" / "files.json").exists() else None
        n_files = len(record_files) if record_files else len(paths)
        all_pairs = n_files * (n_files - 1) // 2
        pooled = {it["key"] for it in pool[n]["items"] if it["kind"] != "random"} | \
                 {pair_key(e["a"], e["b"]) for e in pool[n]["explicit"] if e["note"] == "imports"}
        rand = [it for it in pool[n]["items"] if it["kind"] == "random"]
        y = sum(labels.get(n, {}).get(it["key"], {}).get("label") == "Y" for it in rand)
        unpooled = all_pairs - len(pooled)
        est_missing = y / len(rand) * unpooled if rand else 0.0
        req = sum(e.required for e in gt.edges)
        out[n] = {"files": n_files, "pairs": all_pairs, "pooled": len(pooled), "random_sampled": len(rand),
                  "random_Y": y, "est_missing_required": round(est_missing, 1), "required": req,
                  "completeness": req / (req + est_missing) if req + est_missing else None}
    return out


def hard_negatives(group: list[str]) -> dict:
    hit, tot = Counter(), 0
    for n in group:
        gt, graphs = load(n)
        hard = set(gt.meta.get("hard_negatives", []))
        tot += len(hard)
        for s, g in graphs.items():
            hit[s] += len(hard & set(predicted(g)))
    return {"designed": tot, "linked": dict(hit), "rate": {s: hit[s] / tot for s in hit} if tot else {}}


def confusions(group: list[str]) -> dict:
    out = {}
    for s in ("pipeline", "LLM-only"):
        c = Counter()
        for n in group:
            gt, graphs = load(n)
            if s in graphs:
                for g_rel, p_rel, k in evaluate(graphs[s], gt)["confusion"]:
                    if g_rel != p_rel:
                        c[(g_rel, p_rel)] += k
        out[s] = [[g, p, k] for (g, p), k in c.most_common(8)]
    return out


def pct(x) -> str:
    return "–" if x is None else f"{100 * x:.1f}"


def main() -> None:
    real, mock = names()
    scores = json.loads((RUNS / "bench" / "results" / "scores.json").read_text(encoding="utf-8"))
    res = {"real": {}, "mock": {}}
    md = ["# Benchmark analysis\n", "Generated by `benchmark/analyze.py` from the same graphs and ground truth as "
          "RESULTS.md. Percentages.\n"]
    for tag, group in (("real", real), ("mock", mock)):
        if not group:
            continue
        r = res[tag]
        r["recall_by_type"] = rt = recall_by_type(group)
        types = sorted(rt["total"], key=lambda t: -rt["total"][t])
        md += [f"## {tag} projects\n", "### Recall of required edges by file-type pair\n",
               "| pair type | required | " + " | ".join(rt["recall"]) + " |",
               "|---|---:|" + "---:|" * len(rt["recall"])]
        md += [f"| {t} | {rt['total'][t]} | " + " | ".join(pct(rt["recall"][s].get(t)) for s in rt["recall"]) + " |"
               for t in types]
        md.append("\n### Paired bootstrap over projects (mean difference, 95% CI, projects won/lost)\n")
        md += ["| comparison | metric | mean Δ | 95% CI | won / lost |", "|---|---|---:|---|---:|"]
        r["bootstrap"] = {}
        for a, b in (("pipeline", "LLM-only"), ("pipeline", "no-LLM")):
            for metric in ("f1", "f1_strict", "recall_semantic", "relation_accuracy"):
                bs = bootstrap(scores, group, metric, a, b)
                if bs:
                    r["bootstrap"][f"{a} - {b} {metric}"] = bs
                    md.append(f"| {a} − {b} | {metric} | {100 * bs['mean']:+.1f} | [{100 * bs['lo']:+.1f}, {100 * bs['hi']:+.1f}] "
                              f"| {bs['wins']} / {bs['losses']} |")
        if tag == "real":
            r["completeness"] = comp = completeness(group)
            if comp:
                md += ["\n### Ground-truth completeness (estimated from random pairs)\n",
                       "| project | files | pairs | pooled | random sampled | random labeled Y | est. missing required | required | completeness |",
                       "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
                md += [f"| {n} | {c['files']} | {c['pairs']} | {c['pooled']} | {c['random_sampled']} | {c['random_Y']} | "
                       f"{c['est_missing_required']} | {c['required']} | {pct(c['completeness'])} |" for n, c in comp.items()]
                tot_req = sum(c["required"] for c in comp.values())
                tot_miss = sum(c["est_missing_required"] for c in comp.values())
                md.append(f"\nOverall estimated completeness: {pct(tot_req / (tot_req + tot_miss))} "
                          f"({tot_req} required edges, about {tot_miss:.0f} missed by every pooled system). "
                          "Recall on real projects is measured against the pooled edges, so it is an upper bound.\n")
        else:
            r["hard_negatives"] = hn = hard_negatives(group)
            md += ["\n### Designed hard negatives (decoy files paired with similar-looking files)\n",
                   f"{hn['designed']} decoy pairs. Share linked by each system: " +
                   ", ".join(f"{s} {pct(v)}" for s, v in hn["rate"].items()) + "\n"]
        r["confusions"] = conf = confusions(group)
        md.append("### Most frequent relation-type confusions on matched pairs (ground truth → predicted, count)\n")
        for s, rows in conf.items():
            md.append(f"- {s}: " + "; ".join(f"{g} → {p} ({k})" for g, p, k in rows))
        md.append("")
    (RUNS / "bench" / "results" / "analysis.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    (RUNS / "bench" / "results" / "ANALYSIS.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
