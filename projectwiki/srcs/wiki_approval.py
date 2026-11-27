"""Publish a frozen graph, viewer, and Markdown wiki as one approved version."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from uuid import uuid4

from .. import pipeline
from ..config import Config
from ..models.visualization import export_obsidian
from .feedback import read_events
from .levels import final_graph_from_dict
from .record import Record


APPROVED_DIR = "approved_wiki"


class StaleGraphError(ValueError):
    """The graph changed after the browser loaded it."""


def approve_wiki(out: Path, cfg: Config, revision: str, last_feedback: dict | None = None) -> Path:
    target = out / APPROVED_DIR
    if (target / "view.html").is_file():
        return target

    graph_file = out / "final_graph.json"
    data = graph_file.read_bytes()
    graph = final_graph_from_dict(json.loads(data))
    if graph.revision() != revision:
        raise StaleGraphError("그래프가 바뀌었어요. 화면을 새로고침한 뒤 확인해 주세요.")
    record = Record.load(out)

    package = out / f".approval-{uuid4().hex}"
    package.mkdir()
    try:
        (package / "graph.json").write_text(json.dumps(graph.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
        export_obsidian(graph, record, package / "wiki")
        view = pipeline.render(out, cfg, graph, record, len(read_events(out / "feedback.jsonl")),
                               view_path=package / "view.html")
        report = json.dumps(last_feedback, ensure_ascii=False).replace("</", "<\\/")
        html = view.read_text(encoding="utf-8").replace("<body>", "<body data-approved>", 1)
        html = html.replace("/*__FEEDBACK_RESULT__*/null", report, 1)
        view.write_text(html, encoding="utf-8")
        if graph_file.read_bytes() != data:
            raise StaleGraphError("그래프가 바뀌었어요. 화면을 새로고침한 뒤 확인해 주세요.")
        try:
            package.rename(target)
        except OSError:
            if not (target / "view.html").is_file():
                raise
    finally:
        if package.exists():
            shutil.rmtree(package, ignore_errors=True)
    return target
