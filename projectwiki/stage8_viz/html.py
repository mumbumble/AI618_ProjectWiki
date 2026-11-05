"""Single-file HTML viewer (vis-network) with evidence panels and feedback export."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from ..stage3_record import Record
from ..schema import FEEDBACK_TYPES, Graph

TEMPLATE = Path(__file__).with_name("template.html")
PREVIEW_CHARS = 800

RELATION_NAMES = {
    "imports": "import", "links_to": "링크", "mentions": "언급", "similar": "유사", "user": "사용자 관계",
    "implements": "구현", "describes": "설명", "uses": "사용", "produces": "생성", "extends": "확장·후속",
    "same_method": "같은 방법", "supports": "뒷받침", "contradicts": "반대", "compares": "비교",
    "same_topic": "같은 주제", "duplicate": "중복·다른 버전", "other": "기타",
}


def view_data(graph: Graph, record: Record, meta: dict) -> dict:
    nodes = []
    for n in graph.nodes:
        text = next((c.text for c in record.file_chunks(n.id) if c.kind != "path"), "")
        nodes.append({**asdict(n), "preview": text[:PREVIEW_CHARS]})
    run_id = hashlib.sha1(json.dumps([meta.get("root"), meta.get("created")]).encode()).hexdigest()[:12]
    return {"nodes": nodes, "groups": [asdict(g) for g in graph.groups], "edges": [asdict(e) for e in graph.edges],
            "relations": RELATION_NAMES, "feedback_types": FEEDBACK_TYPES, "meta": {**meta, "run_id": run_id}}


def write_view(graph: Graph, record: Record, path: Path, meta: dict) -> Path:
    data = json.dumps(view_data(graph, record, meta), ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", data, 1)
    path.write_text(html, encoding="utf-8")
    return path
