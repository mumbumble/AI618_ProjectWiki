"""Model stage 5 — visualization: the final graph as an interactive viewer and as an Obsidian vault.

view.html is a single file built from srcs/view_template.html (vis-network); its replay of the user's edits
must follow the same rules as srcs/finalize.py.
"""
from __future__ import annotations

import hashlib
import json
import posixpath
import re
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from ..schema import FEEDBACK_TYPES, VISIBLE_STATUS, Graph
from ..srcs.record import Record


# ---- HTML viewer ---------------------------------------------------------------------------------
TEMPLATE = Path(__file__).resolve().parents[1] / "srcs" / "view_template.html"
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


# ---- Obsidian vault ------------------------------------------------------------------------------


def note_names(paths: list[str]) -> dict[str, str]:
    """Basename without extension, prefixed with parent folders only when needed to stay unique."""
    stems = Counter(posixpath.basename(p) for p in paths)
    out = {}
    for p in paths:
        name = posixpath.basename(p) if stems[posixpath.basename(p)] == 1 else p.replace("/", " - ")
        out[p] = re.sub(r'[\\:*?"<>|#^\[\]]', "_", name)
    return out


def export_obsidian(graph: Graph, record: Record, vault: Path) -> Path:
    vault = Path(vault)
    vault.mkdir(parents=True, exist_ok=True)
    names = note_names([n.path for n in graph.nodes])
    by_id = {n.id: n for n in graph.nodes}
    group_name = {g.id: g.name for g in graph.groups}
    edges = [e for e in graph.edges if e.status in VISIBLE_STATUS]

    for n in graph.nodes:
        tag = re.sub(r"\s+", "_", group_name.get(n.group, "ungrouped"))
        lines = ["---", f"path: \"{n.path}\"", f"type: {n.type}", f"tags: [\"group/{tag}\"]", "---",
                 f"# {posixpath.basename(n.path)}", "", f"원본: `{record.root}/{n.path}`", ""]
        if n.role or n.summary:
            lines += [f"**{n.role}**  " if n.role else "", n.summary, ""]
        lines.append("## 연결")
        for e in edges:
            if n.id not in (e.source, e.target):
                continue
            other = by_id[e.target if e.source == n.id else e.source]
            arrow = "→" if e.source == n.id else "←"
            kind = "직접" if e.direct else "추론"
            lines.append(f"- {arrow} [[{names[other.path]}]] · {RELATION_NAMES.get(e.relation, e.relation)}"
                         f"{' · ' + e.label if e.label else ''} ({kind})")
            for v in e.evidence[:2]:
                lines.append(f"    > {v.quote[:200]} — {posixpath.basename(by_id[v.file_id].path)} {v.locator}")
        (vault / f"{names[n.path]}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    gdir = vault / "_groups"
    gdir.mkdir(exist_ok=True)
    for g in graph.groups:
        body = [f"# {g.name}", "", g.description, ""] + [f"- [[{names[by_id[m].path]}]]" for m in g.members]
        safe = re.sub(r'[\\/:*?"<>|]', "_", g.name)
        (gdir / f"{safe}.md").write_text("\n".join(body) + "\n", encoding="utf-8")
    return vault
