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
FOLDER_TOPICS = {
    "src": "구현 코드", "lib": "라이브러리", "docs": "기술 문서", "paper": "논문",
    "figures": "시각 자료", "experiments": "실험 결과", "notes": "작업 노트",
    "configs": "실행 설정", "tests": "검증 코드", "data": "데이터", "examples": "예제",
}


def descriptive_name(folders: str, types: list[str]) -> str:
    topics = [FOLDER_TOPICS.get(p.rsplit("/", 1)[-1].lower()) for p in folders.split(" + ")]
    if all(topics):
        return " · ".join(dict.fromkeys(topics))
    labels = {"markdown": "문서", "pdf": "참고 문헌", "python": "구현 코드", "image": "시각 자료",
              "notebook": "분석 노트북", "media": "미디어", "text": "텍스트 자료"}
    return " · ".join(label for label, _ in Counter(labels.get(t, "프로젝트 자료") for t in types).most_common(2)) or "파일 그룹"


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
        files = [record.file_by_id[m] for m in g.members]
        g.name = descriptive_name(folder_name([f.path for f in files]), [f.type for f in files])
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
