"""Turn the setup form answers into preferences for a ProjectWiki build."""
from __future__ import annotations

import re
from dataclasses import replace
from heapq import nlargest
from pathlib import PurePosixPath

import numpy as np

from ..schema import FeedbackEvent, Node, Preferences
from .record import Record


def similar_file_pairs(record: Record, limit: int = 3) -> list[tuple[str, str]]:
    """Highest cosine similarities between distinct files with content; one row in memory at a time."""
    indices = sorted((i for i, f in enumerate(record.files)
                      if any(record.chunk_by_id[c].kind != "path" for c in f.chunk_ids)),
                     key=lambda i: record.files[i].path)
    vectors = record.file_emb[indices]

    def candidates():
        for i in range(len(indices) - 1):
            scores = vectors[i + 1:] @ vectors[i]
            for offset in np.argsort(-scores, kind="stable")[:limit]:
                if scores[offset] > 0:
                    yield float(scores[offset]), record.files[indices[i]].id, record.files[indices[i + 1 + offset]].id

    return [(a, b) for _, a, b in nlargest(limit, candidates(), key=lambda pair: pair[0])]


def pair_feedback(pairs: list[tuple[str, str]], answers: list[str], directions: list[str] | None = None) -> list[FeedbackEvent]:
    events = []
    for (a, b), choice, direction in zip(pairs, answers, directions if directions is not None else [""] * len(pairs), strict=True):
        if direction not in ("", "forward", "reverse"):
            raise ValueError("invalid initial pair direction")
        if choice == "skip":
            continue
        if choice == "edge_confirm":
            source, target = (b, a) if direction == "reverse" else (a, b)
            events.append(FeedbackEvent(type=choice, source=source, target=target, set_direction=bool(direction)))
        elif choice == "edge_irrelevant":
            events.append(FeedbackEvent(type=choice, source=a, target=b))
        else:
            raise ValueError("invalid initial pair choice")
    return events


MATERIAL_HINTS = {
    "results": r"결과|그림|그래프|시각화|result|figure|plot",
    "code": r"코드|설정|소스|구현|code|source|config",
    "docs": r"문서|논문|보고서|document|paper|report",
    "notes": r"회의|메모|노트|meeting|memo|notes?",
}


def material_kind(path: str, file_type: str) -> str | None:
    path = path.lower()
    parts = set(re.split(r"[\W_]+", path))
    ext = PurePosixPath(path).suffix
    if parts & {"notes", "note", "meeting", "meetings", "memo"}:
        return "notes"
    if file_type == "image" or parts & {"result", "results", "figures", "plots", "metrics", "outputs"}:
        return "results"
    if file_type in {"python", "notebook"} or ext in {
        ".yaml", ".yml", ".toml", ".ini", ".cfg", ".sh", ".js", ".ts", ".tsx", ".jsx", ".c", ".cpp", ".java", ".go", ".rs"
    } or parts & {"src", "config", "configs"}:
        return "code"
    if file_type in {"markdown", "pdf"} or ext in {".rst", ".tex", ".docx"}:
        return "docs"
    return None


def preferences_from_answers(prefs: Preferences, purpose: str, priority: str, grouping: str) -> Preferences:
    guide = {**prefs.guide, "priority_materials": priority, "grouping_request": grouping}
    if grouping:
        normalized = grouping.lower()
        if re.search(r"시스템에\s*맡기|알아서|automatic", normalized):
            guide.pop("group_by", None)
        elif re.search(r"단계|진행\s*순서|workflow|stage", normalized):
            guide["group_by"] = "workflow"
        elif re.search(r"폴더|디렉터리|디렉토리|folder|directory", normalized):
            guide["group_by"] = "directory"
        elif re.search(r"주제|내용|토픽|topic|content", normalized):
            guide["group_by"] = "content"
    return replace(prefs, purpose=purpose, guide=guide)


def priority_nodes(nodes: list[Node], request: str) -> list[str]:
    if not request:
        return []
    request = request.casefold().replace("\\", "/")
    kinds = {kind for kind, pattern in MATERIAL_HINTS.items() if re.search(pattern, request)}
    named, similar = [], []
    for node in nodes:
        path = PurePosixPath(node.path.casefold())
        if path.suffix and (path.as_posix() in request or path.name in request):
            named.append(node.id)
        elif material_kind(node.path, node.type) in kinds:
            similar.append(node.id)
    return named + similar
