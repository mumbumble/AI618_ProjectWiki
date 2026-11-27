"""User feedback log: one JSON event per line in <out>/feedback.jsonl."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, fields
from pathlib import Path

from .record import Record
from ..schema import LEVELS, FEEDBACK_TYPES, FeedbackEvent, edge_key

log = logging.getLogger(__name__)
FIELDS = {f.name for f in fields(FeedbackEvent)}


def read_events(path: Path) -> list[FeedbackEvent]:
    if not path.exists():
        return []
    events = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        d = json.loads(line)
        if d.get("type") not in FEEDBACK_TYPES:
            log.warning("%s:%d unknown feedback type %r", path, n, d.get("type"))
            continue
        events.append(FeedbackEvent(**{k: v for k, v in d.items() if k in FIELDS}))
    return events


def resolve(events: list[FeedbackEvent], record: Record) -> list[FeedbackEvent]:
    """Map paths to file ids and drop events about files that no longer exist."""
    out = []
    for ev in events:
        if ev.type in ("group_add", "group_delete"):
            if ev.group and (ev.type == "group_delete" or ev.note.strip()):
                out.append(ev)
            continue
        if ev.type == "node_level" and ev.level not in LEVELS:
            log.warning("skipping invalid file level: %s", ev)
            continue
        needed = ("source", "target") if ev.type.startswith("edge_") else ("node",)
        if any(getattr(ev, k) is None for k in needed):
            log.warning("skipping incomplete feedback: %s", ev)
            continue
        ids = {k: record.resolve(getattr(ev, k)) for k in ("source", "target", "node")}
        if any(getattr(ev, k) is not None and ids[k] is None for k in ids):
            log.warning("skipping feedback on missing file: %s", ev)
            continue
        for k, v in ids.items():
            setattr(ev, k, v)
        out.append(ev)
    return out


def merge(log_path: Path, new_events: list[FeedbackEvent]) -> int:
    """Append events not already in the log; returns how many were added."""
    have = {json.dumps(asdict(e), sort_keys=True) for e in read_events(log_path)}
    added = 0
    with open(log_path, "a", encoding="utf-8") as fh:
        for e in new_events:
            e.ts = e.ts or time.strftime("%Y-%m-%dT%H:%M:%S")
            key = json.dumps(asdict(e), sort_keys=True)
            if key not in have:
                fh.write(json.dumps(asdict(e), ensure_ascii=False) + "\n")
                have.add(key)
                added += 1
    return added


class FeedbackInputError(ValueError):
    """The request needs clarification before any edits can be applied."""


def validate_events(items: list[dict], record: Record, existing: set[str]) -> list[FeedbackEvent]:
    paths = {f.path: f.id for f in record.files}
    events = []
    for item in items:
        kind = item.get("type")
        if not isinstance(kind, str) or kind not in FEEDBACK_TYPES:
            raise FeedbackInputError("지원하지 않는 수정 요청이에요.")
        fields = ("source", "target") if kind.startswith("edge_") else ("node",) if kind.startswith("node_") else ()
        values = {}
        for field in fields:
            name = item.get(field)
            if not isinstance(name, str) or not name:
                raise FeedbackInputError("어느 파일을 수정할지 프로젝트 내 경로를 적어 주세요.")
            path = record.file_by_id[name].path if name in record.file_by_id else name.replace("\\", "/")
            if path not in paths:
                raise FeedbackInputError(f"‘{name}’ 파일을 찾지 못했어요. 프로젝트 내 경로를 확인해 주세요.")
            values[field] = paths[path]
        for field in ("relation", "group", "note", "ts", "edit_reason"):
            value = item.get(field)
            if value is not None and (not isinstance(value, str) or len(value) > 1000):
                raise FeedbackInputError("피드백 입력을 확인해 주세요.")
            if value:
                values[field] = value
        if "set_direction" in item:
            if not isinstance(item["set_direction"], bool):
                raise FeedbackInputError("연결 방향을 확인해 주세요.")
            values["set_direction"] = item["set_direction"]
        if kind.startswith("edge_"):
            a, b = values["source"], values["target"]
            if a == b:
                raise FeedbackInputError("서로 다른 두 파일을 지정해 주세요.")
            key = edge_key(a, b)
            if kind != "edge_add" and key not in existing:
                raise FeedbackInputError("지정한 두 파일 사이에 기존 연결이 없어요. 파일 경로를 확인해 주세요.")
            if kind == "edge_add":
                existing.add(key)
        elif kind == "node_level":
            if item.get("level") not in LEVELS:
                raise FeedbackInputError("파일 중요도를 상·중·하 중에서 선택해 주세요.")
            values["level"] = item["level"]
        elif kind == "node_move" and not values.get("group"):
            raise FeedbackInputError("이동할 그룹 이름을 적어 주세요.")
        elif kind.startswith("group_") and (not values.get("group") or
                                            (kind == "group_add" and not values.get("note", "").strip())):
            raise FeedbackInputError("그룹 이름과 대상을 확인해 주세요.")
        events.append(FeedbackEvent(type=kind, **values))
    return events
