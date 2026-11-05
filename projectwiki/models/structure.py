"""Model stage 3 — structure generation: the relation graph between files.

1. candidates (srcs/candidates.py): imports, links, file-name mentions and bge-m3 similarity
2. evidence: the best chunk pair per edge, chosen by bge-reranker-v2-m3
3. judgment: Claude names the relation, its direction and a label, marks it direct or inferred, and quotes
   both sides; quotes that are not found verbatim in the excerpts are discarded
"""
from __future__ import annotations

import logging
from collections import Counter

import numpy as np

from ..config import Config
from ..schema import EXPLICIT, RELATIONS, STRUCTURAL, Edge, Evidence, Graph, Group, Node, edge_key
from ..srcs.candidates import QUOTE_CHARS, reference_candidates, similarity_candidates
from ..srcs.llm import Claude, obj_schema
from ..srcs.record import Record
from .encoder import _device, _load

log = logging.getLogger(__name__)


# ---- evidence reranker ---------------------------------------------------------------------------


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


# ---- relation judgment ---------------------------------------------------------------------------
EXCERPT_CHARS = 1500
JUDGE_SYSTEM = """You check one candidate link between two files in a user's local project folder and describe it.
Use only the summaries and excerpts given. Write the label in {language}.
- keep: true if the link helps the user understand how the project fits together; false if the files are unrelated or the link is trivial.
- relation: the closest type. implements = code realizes a method or design; describes = a document explains the other file; uses = depends on its code, data or results; produces = generates the other file's results or figures; extends = builds on or follows up; same_method; supports = gives evidence for; contradicts; compares; same_topic; duplicate = another version of the same content; other.
- direction: a_to_b if it reads "A <relation> B", b_to_a if it reads "B <relation> A", both if symmetric.
- label: at most twelve words saying how the two files relate.
- direct: true only if an excerpt states the link explicitly (an import, a link, a file-name mention, or a sentence about the other file's content). A shared topic alone is not direct.
- quote_a, quote_b: a short span (under 200 characters) copied exactly from the excerpts of A and of B that supports the link, or an empty string."""
JUDGE_SCHEMA = obj_schema(
    keep={"type": "boolean"},
    relation={"type": "string", "enum": RELATIONS},
    direction={"type": "string", "enum": ["a_to_b", "b_to_a", "both"]},
    label={"type": "string"},
    direct={"type": "boolean"},
    quote_a={"type": "string"},
    quote_b={"type": "string"},
)
REASON_TEXT = {"imports": "an import statement in A", "links_to": "a link in A to B",
               "mentions": "A mentions B's file name", "similar": "embedding similarity between the files"}


def norm(s: str) -> str:
    return " ".join(s.split())


def excerpts(record: Record, fid: str, evidence: list[Evidence]) -> list:
    chunks = [record.chunk_by_id[v.chunk_id] for v in evidence if v.file_id == fid]
    return chunks or record.file_chunks(fid)[:1]


def judge_edges(edges: list[Edge], record: Record, llm: Claude, cfg: Config, purpose: str) -> None:
    system = JUDGE_SYSTEM.format(language=cfg.language)
    todo = sorted(edges, key=lambda e: (e.reason not in EXPLICIT, -e.score))[:cfg.max_judge_edges]
    if len(edges) > len(todo):
        log.warning("judging %d of %d edges (max_judge_edges)", len(todo), len(edges))

    def side(tag: str, fid: str, chunks) -> str:
        f = record.file_by_id[fid]
        body = "\n".join(f"[{c.locator}]\n{c.text[:EXCERPT_CHARS]}" for c in chunks)
        return (f"File {tag}: {f.path} ({f.role or f.type})\nSummary {tag}: {f.summary or f.title}\n"
                f"Excerpts from {tag}:\n<excerpts_{tag.lower()}>\n{body}\n</excerpts_{tag.lower()}>")

    def run(e: Edge):
        a, b = excerpts(record, e.source, e.evidence), excerpts(record, e.target, e.evidence)
        content = (f"User's purpose for this project: {purpose or '(not given)'}\n"
                   f"Why this candidate exists: {REASON_TEXT.get(e.reason, e.reason)}\n\n"
                   f"{side('A', e.source, a)}\n\n{side('B', e.target, b)}")
        return a, b, llm.json(cfg.llm_model, system, content, JUDGE_SCHEMA, key=content)

    for e, (a, b, r) in zip(todo, llm.map(run, todo)):
        if r is None:
            continue
        ok_a = apply_quote(e, a, r["quote_a"])
        ok_b = apply_quote(e, b, r["quote_b"])
        e.relation, e.label = r["relation"], r["label"]
        e.direct = e.reason in EXPLICIT or (r["direct"] and (ok_a or ok_b))
        if r["direction"] == "b_to_a":
            e.source, e.target = e.target, e.source
        if not r["keep"] and e.reason not in STRUCTURAL:
            e.status = "llm_rejected"


def apply_quote(e: Edge, chunks, quote: str) -> bool:
    """Keep the model's quote only if it appears verbatim (up to whitespace) in an excerpt."""
    q = norm(quote)
    if len(q) < 4:
        return False
    for c in chunks:
        if q in norm(c.text):
            for v in e.evidence:
                if v.chunk_id == c.id:
                    v.quote = q
                    return True
            e.evidence.append(Evidence(c.id, c.file_id, c.locator, q))
            return True
    return False


# ---- stage entry ---------------------------------------------------------------------------------


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
