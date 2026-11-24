"""Turn the setup form answers into preferences for a ProjectWiki build."""
from __future__ import annotations

import re
from dataclasses import replace
from pathlib import PurePosixPath

from ..schema import Node, Preferences


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
