"""Project record: the files, chunks and vectors that every model stage after encoding reads, and its on-disk form."""
from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np

from ..schema import Chunk, FileRecord
from ..models.encoder import Encoded


class Record:
    """Everything the model stages need about the project folder."""

    def __init__(self, root: str, files: list[FileRecord], chunks: list[Chunk],
                 chunk_emb: np.ndarray, file_emb: np.ndarray, encoder_id: str):
        self.root, self.files, self.chunks = root, files, chunks
        self.chunk_emb, self.file_emb, self.encoder_id = chunk_emb, file_emb, encoder_id
        self.file_index = {f.id: i for i, f in enumerate(files)}
        self.chunk_index = {c.id: i for i, c in enumerate(chunks)}
        self.file_by_id = {f.id: f for f in files}
        self.file_by_path = {f.path: f for f in files}
        self.chunk_by_id = {c.id: c for c in chunks}

    def file_chunks(self, fid: str) -> list[Chunk]:
        return [self.chunk_by_id[c] for c in self.file_by_id[fid].chunk_ids]

    def resolve(self, ref: str | None) -> str | None:
        """Accept a file id or a project-relative path."""
        if ref is None or ref in self.file_by_id:
            return ref
        f = self.file_by_path.get(ref.replace("\\", "/").lstrip("./"))
        return f.id if f else None

    def save(self, out: Path) -> None:
        d = out / "record"
        d.mkdir(parents=True, exist_ok=True)
        (d / "files.json").write_text(json.dumps([asdict(f) for f in self.files], ensure_ascii=False, indent=1),
                                      encoding="utf-8")
        with open(d / "chunks.jsonl", "w", encoding="utf-8") as fh:
            for c in self.chunks:
                fh.write(json.dumps(asdict(c), ensure_ascii=False) + "\n")
        np.save(d / "chunk_emb.npy", self.chunk_emb)
        np.save(d / "file_emb.npy", self.file_emb)
        meta = {"root": self.root, "encoder": self.encoder_id, "created": time.strftime("%Y-%m-%d %H:%M:%S")}
        (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")

    @classmethod
    def load(cls, out: Path) -> Record:
        d = out / "record"
        files = [FileRecord.from_dict(f) for f in json.loads((d / "files.json").read_text(encoding="utf-8"))]
        chunks = [Chunk(**json.loads(line)) for line in open(d / "chunks.jsonl", encoding="utf-8")]
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        return cls(meta["root"], files, chunks, np.load(d / "chunk_emb.npy"), np.load(d / "file_emb.npy"),
                   meta["encoder"])


def diff_files(out: Path, files: list[FileRecord]) -> dict:
    prev_path = out / "record" / "files.json"
    if not prev_path.exists():
        return {"added": [f.path for f in files], "changed": [], "removed": []}
    prev = {f["path"]: f["sha256"] for f in json.loads(prev_path.read_text(encoding="utf-8"))}
    now = {f.path: f.sha256 for f in files}
    return {"added": sorted(set(now) - set(prev)),
            "changed": sorted(p for p in now if p in prev and prev[p] != now[p]),
            "removed": sorted(set(prev) - set(now))}


def build_record(root: Path, files: list[FileRecord], chunks: list[Chunk], enc: Encoded) -> Record:
    """File vector = mean of its chunk vectors, plus its summary vector when there is one."""
    chunk_row = {c.id: i for i, c in enumerate(chunks)}
    file_emb = np.zeros((len(files), enc.chunk_emb.shape[1]), np.float32)
    for i, f in enumerate(files):
        v = enc.chunk_emb[[chunk_row[c] for c in f.chunk_ids]].mean(0)
        v /= np.linalg.norm(v) + 1e-8
        if f.id in enc.summary_emb:
            v = v + enc.summary_emb[f.id]
        file_emb[i] = v / (np.linalg.norm(v) + 1e-8)
    return Record(str(Path(root).resolve()), files, chunks, enc.chunk_emb, file_emb, enc.encoder_id)
