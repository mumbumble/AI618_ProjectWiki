"""Run the pipeline in order; every intermediate result is written under the output folder.

    files -> srcs/ingest, srcs/enrich -> evidence chunks, image descriptions, summaries
    1 models/encoder        chunks + summaries -> bge-m3 vectors  (srcs/record -> project record)
    2 models/clustering     record + preferences -> groups                       (experimental slot)
    3 models/structure      candidates -> evidence -> Claude judgment -> graph.json
    4 models/preference     graph + feedback -> correction                       (experimental slot)
      srcs/finalize         graph + correction + explicit edits -> final_graph.json
    5 models/visualization  final graph -> view.html
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import Config
from .models.clustering import get_clusterer
from .models.encoder import encode_record
from .models.preference import get_corrector
from .models.structure import build_graph
from .models.visualization import write_view
from .schema import VISIBLE_STATUS, FeedbackEvent, Graph, Preferences
from .srcs.enrich import describe_images, summarize
from .srcs.feedback import merge, read_events, resolve
from .srcs.feedback_changes import feedback_changes
from .srcs.finalize import finalize
from .srcs.ingest import ingest
from .srcs.initial_preferences import priority_nodes
from .srcs.levels import assign_levels, final_graph_from_dict
from .srcs.llm import Claude
from .srcs.naming import name_groups
from .srcs.record import Record, build_record, diff_files

log = logging.getLogger(__name__)


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def make_llm(cfg: Config, out: Path, client=None) -> Claude | None:
    if not cfg.llm:
        return None
    if client is None and cfg.llm_backend == "cli":
        from .srcs.claude_cli import ClaudeCodeClient
        client = ClaudeCodeClient()
        cfg.llm_workers = min(cfg.llm_workers, 4)  # each call is a separate CLI process
    elif client is None and not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY is not set. Set it, use --llm-backend cli (logged-in Claude Code), "
                         "or pass --no-llm to skip the Claude steps.")
    return Claude(cfg, out / "cache" / "llm.json", client=client)


@dataclass
class PreparedProject:
    record: Record
    llm: Claude | None
    changes: dict
    seconds: dict


def prepare_project(root: Path, out: Path, cfg: Config, llm_client=None) -> PreparedProject:
    """Read and encode files once, before any preference-dependent stages."""
    root = Path(root).resolve()
    out.mkdir(parents=True, exist_ok=True)
    cfg.save(out / "config.json")
    llm = make_llm(cfg, out, llm_client)
    times, t = {}, time.time()

    def lap(name: str) -> None:
        nonlocal t
        times[name] = round(time.time() - t, 2)
        t = time.time()

    files, chunks = ingest(root, cfg)  # files -> chunks
    if llm is not None and cfg.describe_images:
        describe_images(root, files, chunks, llm, cfg)
    changes = diff_files(out, files)
    log.info("changes since last run: %d added, %d changed, %d removed",
             len(changes["added"]), len(changes["changed"]), len(changes["removed"]))
    lap("ingest")
    if llm is not None and cfg.summarize:  # summaries are encoded together with the chunks
        summarize(files, chunks, llm, cfg)
    lap("summaries")
    encoded = encode_record(files, chunks, cfg, out / "cache")  # 1 encoding
    changes["encoded"] = encoded.new
    lap("1 encoding")
    record = build_record(root, files, chunks, encoded)  # project record
    record.save(out)
    return PreparedProject(record, llm, changes, times)


def build(root: Path, out: Path, cfg: Config, prefs: Preferences, llm_client=None) -> dict:
    return build_prepared(prepare_project(root, out, cfg, llm_client), out, cfg, prefs)


def build_prepared(project: PreparedProject, out: Path, cfg: Config, prefs: Preferences,
                   initial_feedback: list[FeedbackEvent] | None = None) -> dict:
    record, llm, changes = project.record, project.llm, project.changes
    times = dict(project.seconds)
    write_json(out / "prefs.json", asdict(prefs))
    t = time.time()

    groups = get_clusterer(cfg.clusterer, cfg).cluster(record, prefs)  # 2 clustering
    name_groups(groups, record, llm, cfg)
    times["2 clustering"] = round(time.time() - t, 2)
    t = time.time()
    purpose = prefs.purpose
    for label, key in (("Materials to prioritize", "priority_materials"), ("Requested grouping", "grouping_request")):
        if answer := prefs.guide.get(key):
            purpose = f"{purpose}\n{label}: {answer}".lstrip()
    graph = build_graph(record, groups, cfg, llm, purpose)  # 3 structure
    write_json(out / "graph.json", graph.to_dict())
    times["3 structure"] = round(time.time() - t, 2)
    t = time.time()
    if initial_feedback:
        previous = resolve(read_events(out / "feedback.jsonl"), record)
        baseline = get_corrector(cfg.corrector, cfg).correct(graph, previous, record)
        before = finalize(graph, baseline, previous, cfg)
    result = correct(out, cfg, record=record, graph=graph, new_feedback=initial_feedback)
    if initial_feedback:
        result["initial_changes"] = feedback_changes(before, result["graph"], initial_feedback, cfg.corrector)
    times["4-5 preference, final graph, view"] = round(time.time() - t, 2)
    result["changes"] = changes
    if llm is not None:
        llm.save()
        result["llm_cost"] = llm.cost_report()
        log.info("LLM usage: %s", result["llm_cost"])
    write_json(out / "run_info.json", {"finished": time.strftime("%Y-%m-%d %H:%M:%S"), "seconds": times,
                                       "changes": changes, "llm": result.get("llm_cost", "off")})
    return result


def correct(out: Path, cfg: Config, record: Record | None = None, graph: Graph | None = None,
            new_feedback: list[FeedbackEvent] | None = None) -> dict:
    """Preference reflection, final graph and viewer from the saved record and graph, after merging new feedback."""
    record = record or Record.load(out)
    graph = graph or Graph.from_dict(json.loads((out / "graph.json").read_text(encoding="utf-8")))
    log_path = out / "feedback.jsonl"
    if new_feedback:
        log.info("added %d new feedback events", merge(log_path, new_feedback))
    feedback = resolve(read_events(log_path), record)

    correction = get_corrector(cfg.corrector, cfg).correct(graph, feedback, record)  # 4 preference
    final = finalize(graph, correction, feedback, cfg)  # final graph: explicit edits always win
    assign_levels(final)
    write_json(out / "correction.json", asdict(correction))
    write_json(out / "final_graph.json", final.to_dict())
    view = render(out, cfg, final, record, len(feedback))  # 5 visualization
    visible = sum(e.status in VISIBLE_STATUS for e in final.edges)
    log.info("final graph: %d files, %d groups, %d edges shown (%d kept for inspection) -> %s",
             len(final.nodes), len(final.groups), visible, len(final.edges) - visible, view)
    return {"view": view, "graph": final, "feedback": len(feedback)}


def render(out: Path, cfg: Config, final: Graph, record: Record, n_feedback: int,
           view_path: Path | None = None) -> Path:
    meta = {"root": record.root, "created": time.strftime("%Y-%m-%d %H:%M:%S"), "encoder": record.encoder_id,
            "clusterer": cfg.clusterer, "corrector": cfg.corrector, "feedback": n_feedback,
            "revision": final.revision(),
            "llm": f"{cfg.llm_model} / {cfg.llm_small_model}" if cfg.llm else "off"}
    prefs_path = out / "prefs.json"
    if prefs_path.is_file():
        prefs = Preferences(**json.loads(prefs_path.read_text(encoding="utf-8")))
        if prefs.purpose or "priority_materials" in prefs.guide:
            request = prefs.guide.get("priority_materials", "")
            meta["setup"] = {"purpose": prefs.purpose, "priority": request,
                             "files": priority_nodes(final.nodes, request)}
    return write_view(final, record, view_path or out / "view.html", meta)


def view(out: Path) -> Path:
    cfg = Config.load(out / "config.json")
    final = final_graph_from_dict(json.loads((out / "final_graph.json").read_text(encoding="utf-8")))
    return render(out, cfg, final, Record.load(out), len(read_events(out / "feedback.jsonl")))
