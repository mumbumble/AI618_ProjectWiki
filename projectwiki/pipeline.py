"""Run the stages end to end; every intermediate result is written under the output folder."""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict
from pathlib import Path

from .cluster import get_clusterer
from .config import Config
from .correct import get_corrector
from .feedback import merge, read_events, resolve
from .finalize import finalize
from .graph import build_graph
from .groups import name_groups
from .models import Claude
from .record import Record, build_record
from .schema import VISIBLE_STATUS, FeedbackEvent, Graph, Preferences
from .viz import write_view

log = logging.getLogger(__name__)


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def make_llm(cfg: Config, out: Path, client=None) -> Claude | None:
    if not cfg.llm:
        return None
    if client is None and cfg.llm_backend == "cli":
        from .models import ClaudeCodeClient
        client = ClaudeCodeClient()
        cfg.llm_workers = min(cfg.llm_workers, 4)  # each call is a separate CLI process
    elif client is None and not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY is not set. Set it, use --llm-backend cli (logged-in Claude Code), "
                         "or pass --no-llm to skip the Claude stages.")
    return Claude(cfg, out / "cache" / "llm.json", client=client)


def build(root: Path, out: Path, cfg: Config, prefs: Preferences, llm_client=None) -> dict:
    """Stages 1-8."""
    out.mkdir(parents=True, exist_ok=True)
    cfg.save(out / "config.json")
    write_json(out / "prefs.json", asdict(prefs))
    llm = make_llm(cfg, out, llm_client)

    times, t = {}, time.time()

    def lap(name: str) -> None:
        nonlocal t
        times[name] = round(time.time() - t, 2)
        t = time.time()

    record, changes = build_record(root, out, cfg, llm)  # 1-3
    lap("1-3 record")
    groups = get_clusterer(cfg.clusterer, cfg).cluster(record, prefs)  # 4
    name_groups(groups, record, llm, cfg)
    lap("4 clustering")
    graph = build_graph(record, groups, cfg, llm, prefs.purpose)  # 5
    write_json(out / "graph.json", graph.to_dict())
    lap("5 graph")
    result = correct(out, cfg, record=record, graph=graph)  # 6-8
    lap("6-8 correct, final, view")
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
    """Stages 6-8 from the saved record and graph, after merging any new feedback into the log."""
    record = record or Record.load(out)
    graph = graph or Graph.from_dict(json.loads((out / "graph.json").read_text(encoding="utf-8")))
    log_path = out / "feedback.jsonl"
    if new_feedback:
        log.info("added %d new feedback events", merge(log_path, new_feedback))
    feedback = resolve(read_events(log_path), record)

    correction = get_corrector(cfg.corrector, cfg).correct(graph, feedback, record)  # 6
    final = finalize(graph, correction, feedback, cfg)  # 7
    write_json(out / "correction.json", asdict(correction))
    write_json(out / "final_graph.json", final.to_dict())
    view = render(out, cfg, final, record, len(feedback))  # 8
    visible = sum(e.status in VISIBLE_STATUS for e in final.edges)
    log.info("final graph: %d files, %d groups, %d edges shown (%d kept for inspection) -> %s",
             len(final.nodes), len(final.groups), visible, len(final.edges) - visible, view)
    return {"view": view, "graph": final, "feedback": len(feedback)}


def render(out: Path, cfg: Config, final: Graph, record: Record, n_feedback: int) -> Path:
    meta = {"root": record.root, "created": time.strftime("%Y-%m-%d %H:%M:%S"), "encoder": record.encoder_id,
            "clusterer": cfg.clusterer, "corrector": cfg.corrector, "feedback": n_feedback,
            "llm": f"{cfg.llm_model} / {cfg.llm_small_model}" if cfg.llm else "off"}
    return write_view(final, record, out / "view.html", meta)


def view(out: Path) -> Path:
    cfg = Config.load(out / "config.json")
    final = Graph.from_dict(json.loads((out / "final_graph.json").read_text(encoding="utf-8")))
    return render(out, cfg, final, Record.load(out), len(read_events(out / "feedback.jsonl")))
