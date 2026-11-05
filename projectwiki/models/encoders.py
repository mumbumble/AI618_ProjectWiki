"""Stage 2 encoders: bge-m3 dense embeddings (TF-IDF only for tests)."""
from __future__ import annotations

import logging

import numpy as np

from ..config import Config

log = logging.getLogger(__name__)


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
