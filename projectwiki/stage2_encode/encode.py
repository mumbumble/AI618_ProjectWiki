"""Stage 2: encode chunks (and summaries) with bge-m3, keeping a cache keyed by text hash.

A refresh only encodes chunks whose text is new. Summaries are encoded in the same call so that every vector
comes from the same encoder (the TF-IDF test encoder is fit per call).
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..config import Config
from ..models import make_encoder
from ..schema import Chunk, FileRecord

log = logging.getLogger(__name__)


@dataclass
class Encoded:
    chunk_emb: np.ndarray  # one row per chunk, in chunk order
    summary_emb: dict  # file id -> summary vector, for files with a summary
    encoder_id: str
    new: int  # texts actually encoded in this run (the rest came from the cache)


def sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def chunk_text(path: str, c: Chunk) -> str:
    return f"{path} | {c.locator}\n{c.text}"


def summary_text(f: FileRecord) -> str:
    return f"{f.path}\n{f.role}\n{f.summary}"


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


def encode_record(files: list[FileRecord], chunks: list[Chunk], cfg: Config, cache_dir: Path) -> Encoded:
    path_of = {f.id: f.path for f in files}
    summary_files = [f for f in files if f.summary]
    texts = [chunk_text(path_of[c.file_id], c) for c in chunks] + [summary_text(f) for f in summary_files]
    emb, enc_id, new = encode_cached(cfg, texts, cache_dir)
    return Encoded(emb[:len(chunks)], dict(zip((f.id for f in summary_files), emb[len(chunks):])), enc_id, new)
