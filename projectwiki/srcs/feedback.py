"""User feedback log: one JSON event per line in <out>/feedback.jsonl."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, fields
from pathlib import Path

from .record import Record
from ..schema import FEEDBACK_TYPES, FeedbackEvent

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
