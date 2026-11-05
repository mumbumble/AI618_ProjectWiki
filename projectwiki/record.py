"""Stages 2-3: describe and summarize files with Claude, encode chunks with bge-m3,
and keep the project record (files, chunks, embeddings) on disk."""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np

from .config import Config
from .ingest import ingest
from .models import Claude, make_encoder, obj_schema
from .schema import Chunk, FileRecord

log = logging.getLogger(__name__)

SUMMARY_SYSTEM = """You summarize one file from a user's local project folder so the user can see its role in the project at a glance.
Write in {language}.
- summary: two or three sentences on what the file contains and what it is for in the project.
- role: a short noun phrase for the file's role, such as "training script", "related-work notes", "experiment results", "paper draft", "meeting notes"."""

IMAGE_SYSTEM = """You describe one image file from a user's local project folder so it can be searched and linked to the files that use it.
Write in {language}.
- description: two to four sentences on what the image shows, including any visible title, labels, axes, legend or text.
- role: a short noun phrase such as "pipeline diagram", "result plot", "qualitative comparison", "screenshot", "photo"."""

SUMMARY_SCHEMA = obj_schema(summary={"type": "string"}, role={"type": "string"})
IMAGE_SCHEMA = obj_schema(description={"type": "string"}, role={"type": "string"})
SUMMARY_CHARS = 8000
MAX_IMAGE_SIDE = 1568
MAX_IMAGE_BYTES = 4_500_000


def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


class Record:
    """Stage 3 output: everything later stages need about the project folder."""

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


def image_block(path: Path) -> dict | None:
    """Downscale an image with PyMuPDF and wrap it as a base64 PNG content block."""
    import pymupdf
    pix = pymupdf.Pixmap(str(path))
    if pix.colorspace and pix.colorspace.n > 3:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    if pix.alpha:
        pix = pymupdf.Pixmap(pix, 0)
    n = 0
    while max(pix.width, pix.height) >> n > MAX_IMAGE_SIDE:
        n += 1
    if n:
        pix.shrink(n)
    data = pix.tobytes("png")
    if len(data) > MAX_IMAGE_BYTES:
        return None
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                        "data": base64.b64encode(data).decode()}}


def describe_images(root: Path, files: list[FileRecord], chunk_by_id: dict, llm: Claude, cfg: Config) -> None:
    targets = [f for f in files if f.type == "image" and not f.path.lower().endswith(".svg")][:cfg.max_images]
    system = IMAGE_SYSTEM.format(language=cfg.language)

    def run(f: FileRecord):
        try:
            block = image_block(root / f.path)
        except Exception as e:
            log.warning("could not read image %s: %s", f.path, e)
            return None
        if block is None:
            return None
        return llm.json(cfg.llm_model, system, [block, {"type": "text", "text": f"Path: {f.path}"}],
                        IMAGE_SCHEMA, key=f"image:{f.sha256}:{cfg.language}", max_tokens=2000)

    for f, r in zip(targets, llm.map(run, targets)):
        if r:  # the image's path-only chunk becomes a description chunk
            c = chunk_by_id[f.chunk_ids[0]]
            c.kind, c.locator, c.text = "figure", "image description", r["description"]
            f.summary, f.role = r["description"], r["role"]
    log.info("described %d images", sum(1 for f in targets if f.summary))


def summarize(files: list[FileRecord], chunk_by_id: dict, llm: Claude, cfg: Config) -> None:
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


def encode_cached(cfg: Config, texts: list[str], cache_dir: Path) -> tuple[np.ndarray, str, int]:
    """Encode with an on-disk cache keyed by text hash, so a refresh only encodes new or changed chunks.

    Returns (vectors, encoder id, number of texts that were actually encoded)."""
    if cfg.encoder == "tfidf":
        enc = make_encoder(cfg)
        return enc.encode(texts), enc.id, len(texts)
    enc_id = f"{cfg.encoder_model}@{cfg.max_length}"
    path = cache_dir / f"emb_{sha1(enc_id)[:8]}.npz"
    cache = {}
    if path.exists():
        z = np.load(path)
        cache = dict(zip(z["keys"].tolist(), z["vecs"]))
    keys = [sha1(t) for t in texts]
    text_of = dict(zip(keys, texts))
    missing = [k for k in dict.fromkeys(keys) if k not in cache]
    if missing:
        log.info("encoding %d new chunks (%d cached)", len(missing), len(keys) - len(missing))
        vecs = make_encoder(cfg).encode([text_of[k] for k in missing])
        cache.update(zip(missing, vecs))
        cache_dir.mkdir(parents=True, exist_ok=True)
        np.savez(path, keys=np.array(list(cache)), vecs=np.stack(list(cache.values())))
    return np.stack([cache[k] for k in keys]), enc_id, len(missing)


def diff_files(out: Path, files: list[FileRecord]) -> dict:
    prev_path = out / "record" / "files.json"
    if not prev_path.exists():
        return {"added": [f.path for f in files], "changed": [], "removed": []}
    prev = {f["path"]: f["sha256"] for f in json.loads(prev_path.read_text(encoding="utf-8"))}
    now = {f.path: f.sha256 for f in files}
    return {"added": sorted(set(now) - set(prev)),
            "changed": sorted(p for p in now if p in prev and prev[p] != now[p]),
            "removed": sorted(set(prev) - set(now))}


def build_record(root: Path, out: Path, cfg: Config, llm: Claude | None) -> tuple[Record, dict]:
    root = Path(root).resolve()
    files, chunks = ingest(root, cfg)
    changes = diff_files(out, files)
    log.info("changes since last run: %d added, %d changed, %d removed",
             len(changes["added"]), len(changes["changed"]), len(changes["removed"]))
    chunk_by_id = {c.id: c for c in chunks}
    if llm is not None:
        if cfg.describe_images:
            describe_images(root, files, chunk_by_id, llm, cfg)
        if cfg.summarize:
            summarize(files, chunk_by_id, llm, cfg)

    file_by_id = {f.id: f for f in files}
    texts = [f"{file_by_id[c.file_id].path} | {c.locator}\n{c.text}" for c in chunks]
    summary_files = [f for f in files if f.summary]
    texts += [f"{f.path}\n{f.role}\n{f.summary}" for f in summary_files]
    emb, enc_id, changes["encoded"] = encode_cached(cfg, texts, out / "cache")
    chunk_emb, summary_emb = emb[:len(chunks)], dict(zip((f.id for f in summary_files), emb[len(chunks):]))

    # file vector: mean of its chunk vectors, plus its summary vector when there is one
    chunk_row = {c.id: i for i, c in enumerate(chunks)}
    file_emb = np.zeros((len(files), emb.shape[1]), np.float32)
    for i, f in enumerate(files):
        v = chunk_emb[[chunk_row[c] for c in f.chunk_ids]].mean(0)
        v /= np.linalg.norm(v) + 1e-8
        if f.id in summary_emb:
            v = v + summary_emb[f.id]
        file_emb[i] = v / (np.linalg.norm(v) + 1e-8)
    record = Record(str(root), files, chunks, chunk_emb, file_emb, enc_id)
    record.save(out)
    return record, changes
