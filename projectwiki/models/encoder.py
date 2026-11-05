"""Model stage 1 — encoding: bge-m3 dense vectors for evidence chunks and file summaries.

Vectors are cached by text hash, so a refresh only encodes new or changed text. Summaries are encoded in the
same call as the chunks so every vector comes from one encoder (the TF-IDF test encoder is fit per call).
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..config import Config
from ..schema import Chunk, FileRecord

log = logging.getLogger(__name__)


# ---- encoders ------------------------------------------------------------------------------------


def _device():
    import torch
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _load(cls, name: str, device: str):
    model = cls.from_pretrained(name)
    return (model.half() if device == "cuda" else model).to(device).eval()


class BgeM3Encoder:
    """Dense bge-m3 embeddings: normalized [CLS] vectors, as in the official dense mode."""
    cacheable = True

    def __init__(self, cfg: Config):
        from transformers import AutoModel, AutoTokenizer
        self.device = _device()
        self.tok = AutoTokenizer.from_pretrained(cfg.encoder_model)
        self.model = _load(AutoModel, cfg.encoder_model, self.device)
        self.batch_size, self.max_length = cfg.batch_size, cfg.max_length
        self.id = f"{cfg.encoder_model}@{cfg.max_length}"
        log.info("loaded %s on %s", cfg.encoder_model, self.device)

    def encode(self, texts: list[str]) -> np.ndarray:
        import torch
        out = np.zeros((len(texts), self.model.config.hidden_size), np.float32)
        order = sorted(range(len(texts)), key=lambda i: -len(texts[i]))  # similar lengths per batch
        with torch.inference_mode():
            for s in range(0, len(order), self.batch_size):
                idx = order[s:s + self.batch_size]
                batch = self.tok([texts[i] for i in idx], padding=True, truncation=True,
                                 max_length=self.max_length, return_tensors="pt").to(self.device)
                cls = self.model(**batch).last_hidden_state[:, 0].float()
                out[idx] = torch.nn.functional.normalize(cls, dim=-1).cpu().numpy()
        return out


class TfidfEncoder:
    """Character n-gram TF-IDF + SVD. Only for tests and machines without the model weights."""
    cacheable = False
    id = "tfidf"

    def __init__(self, cfg: Config):
        pass

    def encode(self, texts: list[str]) -> np.ndarray:
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.preprocessing import normalize
        x = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True).fit_transform(texts)
        k = min(256, x.shape[0] - 1, x.shape[1] - 1)
        x = TruncatedSVD(n_components=k, random_state=0).fit_transform(x) if k >= 2 else x.toarray()
        return normalize(x).astype(np.float32)


def make_encoder(cfg: Config):
    if cfg.encoder == "tfidf":
        return TfidfEncoder(cfg)
    if cfg.encoder == "bge-m3":
        return BgeM3Encoder(cfg)
    raise ValueError(f"unknown encoder {cfg.encoder!r}")


# ---- encoding with a cache -----------------------------------------------------------------------


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
