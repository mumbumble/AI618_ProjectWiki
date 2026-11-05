"""Stage 3: Claude writes a short summary and a role for every text file."""
from __future__ import annotations

import logging

from ..config import Config
from ..models import Claude, obj_schema
from ..schema import FileRecord

log = logging.getLogger(__name__)
SUMMARY_SYSTEM = """You summarize one file from a user's local project folder so the user can see its role in the project at a glance.
Write in {language}.
- summary: two or three sentences on what the file contains and what it is for in the project.
- role: a short noun phrase for the file's role, such as "training script", "related-work notes", "experiment results", "paper draft", "meeting notes"."""
SUMMARY_SCHEMA = obj_schema(summary={"type": "string"}, role={"type": "string"})
SUMMARY_CHARS = 8000


def summarize(files: list[FileRecord], chunks: list, llm: Claude, cfg: Config) -> None:
    chunk_by_id = {c.id: c for c in chunks}
    targets = [f for f in files if not f.summary and chunk_by_id[f.chunk_ids[0]].kind != "path"]
    system = SUMMARY_SYSTEM.format(language=cfg.language)

    def run(f: FileRecord):
        text = ""
        for cid in f.chunk_ids:
            c = chunk_by_id[cid]
            piece = f"[{c.locator}]\n{c.text}\n\n"
            if text and len(text) + len(piece) > SUMMARY_CHARS:
                break
            text += piece[:SUMMARY_CHARS]
        content = f"Path: {f.path}\nType: {f.type}\n\n<file>\n{text}</file>"
        return llm.json(cfg.llm_small_model, system, content, SUMMARY_SCHEMA,
                        key=f"summary:{f.sha256}:{cfg.language}", max_tokens=2000)

    for f, r in zip(targets, llm.map(run, targets)):
        if r:
            f.summary, f.role = r["summary"], r["role"]
    log.info("summarized %d files", sum(1 for f in targets if f.summary))
