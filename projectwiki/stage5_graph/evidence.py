"""Stage 5, step 2: evidence — the best chunk pair per edge, chosen by bge-reranker-v2-m3."""
from __future__ import annotations

import numpy as np

from ..config import Config
from ..models import Reranker
from ..schema import Edge, Evidence
from ..stage3_record import Record
from .candidates import QUOTE_CHARS
RERANK_CHARS = 1200


def choose_evidence(edges: list[Edge], anchors: dict, record: Record, reranker: Reranker | None, cfg: Config):
    """Pick the best (source chunk, target chunk) pair per edge; rerank the top cosine pairs.

    anchors maps edge id -> source chunk id when a reference fixes the source side.
    """
    jobs = []  # (edge, [(chunk a, chunk b, cosine)])
    for e in edges:
        a_ids = [anchors[e.id]] if e.id in anchors else record.file_by_id[e.source].chunk_ids
        b_ids = record.file_by_id[e.target].chunk_ids
        ea = record.chunk_emb[[record.chunk_index[c] for c in a_ids]]
        eb = record.chunk_emb[[record.chunk_index[c] for c in b_ids]]
        sim = ea @ eb.T
        flat = np.argsort(-sim, axis=None)[:cfg.rerank_pairs]
        pairs = [(a_ids[k // len(b_ids)], b_ids[k % len(b_ids)], float(sim.flat[k])) for k in flat]
        jobs.append((e, pairs))
    if reranker is not None:
        texts = [(record.chunk_by_id[a].text[:RERANK_CHARS], record.chunk_by_id[b].text[:RERANK_CHARS])
                 for _, pairs in jobs for a, b, _ in pairs]
        scores = iter(reranker.score(texts)) if texts else iter(())
        jobs = [(e, [(a, b, float(next(scores))) for a, b, _ in pairs]) for e, pairs in jobs]
    for e, pairs in jobs:
        a, b, s = max(pairs, key=lambda p: p[2])
        ca, cb = record.chunk_by_id[a], record.chunk_by_id[b]
        quote_a = e.evidence[0].quote if e.evidence else ca.text[:QUOTE_CHARS]
        e.evidence = [Evidence(a, ca.file_id, ca.locator, quote_a),
                      Evidence(b, cb.file_id, cb.locator, " ".join(cb.text[:QUOTE_CHARS].split()))]
        if e.reason == "similar":
            e.score = s
