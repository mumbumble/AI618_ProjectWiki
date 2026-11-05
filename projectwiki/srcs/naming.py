"""Clustering helper: name the groups a clusterer returns (shared by every clustering method)."""
from __future__ import annotations

import posixpath
from collections import Counter

from ..config import Config
from .llm import Claude, obj_schema
from ..schema import Group
from .record import Record
GROUP_SYSTEM = """You name one group of files from a user's local project folder.
Write in {language}.
- name: at most five words for what these files have in common within the project.
- description: one sentence on what the group holds."""
GROUP_SCHEMA = obj_schema(name={"type": "string"}, description={"type": "string"})
MAX_MEMBERS = 40


def folder_name(paths: list[str]) -> str:
    dirs = [posixpath.dirname(p) for p in paths]
    if all(dirs):
        common = posixpath.commonpath(dirs)
        if common:
            return common
    top = Counter(d.split("/")[0] if d else "(root)" for d in dirs).most_common(2)
    return " + ".join(name for name, _ in top)


def name_groups(groups: list[Group], record: Record, llm: Claude | None, cfg: Config) -> None:
    todo = [g for g in groups if not g.name]
    for g in todo:
        g.name = folder_name([record.file_by_id[m].path for m in g.members])
    if llm is None or not cfg.name_groups:
        return
    system = GROUP_SYSTEM.format(language=cfg.language)

    def run(g: Group):
        lines = []
        for m in g.members[:MAX_MEMBERS]:
            f = record.file_by_id[m]
            lines.append(f"- {f.path} ({f.role or f.type}): {f.summary[:300] or f.title}")
        content = "Files in the group:\n" + "\n".join(lines)
        return llm.json(cfg.llm_small_model, system, content, GROUP_SCHEMA, key=content, max_tokens=1500)

    for g, r in zip(todo, llm.map(run, todo)):
        if r:
            g.name, g.description = r["name"], r["description"]
