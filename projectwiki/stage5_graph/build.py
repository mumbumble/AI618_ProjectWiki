"""Stage 5: build the relation graph — candidates, then evidence, then judgment."""
from __future__ import annotations

import logging
from collections import Counter

from ..config import Config
from ..models import Claude, Reranker
from ..schema import EXPLICIT, Edge, Evidence, Graph, Group, Node, edge_key
from ..stage3_record import Record
from .candidates import reference_candidates, similarity_candidates
from .evidence import choose_evidence
from .judge import judge_edges

log = logging.getLogger(__name__)


def build_graph(record: Record, groups: list[Group], cfg: Config, llm: Claude | None = None,
                purpose: str = "") -> Graph:
    group_of = {m: g.id for g in groups for m in g.members}
    edges: dict[str, Edge] = {}
    anchors: dict[str, str] = {}

    def add(src: str, dst: str, reason: str, score: float, chunk_id: str | None = None, quote: str = ""):
        key = edge_key(src, dst)
        e = edges.get(key)
        rank = {"imports": 3, "links_to": 3, "mentions": 2, "similar": 1}
        if e is None or rank[reason] > rank[e.reason]:
            evidence = []
            if chunk_id:
                c = record.chunk_by_id[chunk_id]
                evidence = [Evidence(chunk_id, src, c.locator, quote)]
                anchors[key] = chunk_id
            edges[key] = Edge(id=key, source=src, target=dst, relation=reason, reason=reason,
                              direct=reason in EXPLICIT, score=score, evidence=evidence)

    for src, dst, reason, chunk_id, quote in reference_candidates(record):
        add(src, dst, reason, 1.0, chunk_id, quote)
    for i, j, s in similarity_candidates(record, group_of, cfg):
        add(record.files[i].id, record.files[j].id, "similar", s)
    edge_list = list(edges.values())
    log.info("candidate edges: %s", dict(Counter(e.reason for e in edge_list)))

    reranker = Reranker(cfg) if cfg.reranker and cfg.encoder != "tfidf" and edge_list else None
    choose_evidence(edge_list, anchors, record, reranker, cfg)
    if llm is not None and cfg.judge and edge_list:
        judge_edges(edge_list, record, llm, cfg, purpose)
        log.info("judge kept %d of %d edges", sum(e.status == "proposed" for e in edge_list), len(edge_list))

    nodes = [Node(id=f.id, path=f.path, type=f.type, title=f.title, group=group_of.get(f.id),
                  role=f.role, summary=f.summary) for f in record.files]
    return Graph(nodes=nodes, groups=groups, edges=edge_list)
