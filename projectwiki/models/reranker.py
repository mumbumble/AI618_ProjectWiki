"""Stage 5 evidence reranker: bge-reranker-v2-m3 cross-encoder."""
from __future__ import annotations

import logging

import numpy as np

from ..config import Config
from .encoders import _device, _load

log = logging.getLogger(__name__)


class Reranker:
    """bge-reranker-v2-m3: relevance of passage b to query a, in [0, 1]."""

    def __init__(self, cfg: Config, batch_size: int = 16, max_length: int = 1024):
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        self.device = _device()
        self.tok = AutoTokenizer.from_pretrained(cfg.reranker)
        self.model = _load(AutoModelForSequenceClassification, cfg.reranker, self.device)
        self.batch_size, self.max_length = batch_size, max_length
        log.info("loaded %s on %s", cfg.reranker, self.device)

    def score(self, pairs: list[tuple[str, str]]) -> np.ndarray:
        import torch
        out = np.zeros(len(pairs), np.float32)
        with torch.inference_mode():
            for s in range(0, len(pairs), self.batch_size):
                a, b = zip(*pairs[s:s + self.batch_size])
                batch = self.tok(list(a), list(b), padding=True, truncation=True,
                                 max_length=self.max_length, return_tensors="pt").to(self.device)
                logits = self.model(**batch).logits.view(-1).float()
                out[s:s + len(a)] = torch.sigmoid(logits).cpu().numpy()
        return out
