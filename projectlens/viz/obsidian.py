"""Export the final graph as an Obsidian vault: one note per file, links as [[wikilinks]], groups as tags."""
from __future__ import annotations

import posixpath
import re
from collections import Counter
from pathlib import Path

from ..record import Record
from ..schema import VISIBLE_STATUS, Graph
from .html import RELATION_NAMES


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
