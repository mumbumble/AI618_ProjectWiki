"""Stage 5: build the relation graph.

1. Candidate edges from explicit references (imports, links, file-name mentions) and bge-m3 similarity
   (top-k inside each group, one strong neighbour across groups).
2. Evidence: the best chunk pair per edge, chosen by bge-reranker-v2-m3.
3. Judgment: Claude Sonnet 5.5 names the relation, its direction and a label, marks it direct or inferred,
   and quotes both sides; quotes that are not in the excerpts are discarded.
"""
from __future__ import annotations

import logging
import posixpath
import re
import urllib.parse
from collections import Counter

import numpy as np

from .config import Config
from .llm import Claude, obj_schema
from .models import Reranker
from .record import Record
from .schema import Edge, Evidence, Graph, Group, Node, edge_key

log = logging.getLogger(__name__)

RELATIONS = ["implements", "describes", "uses", "produces", "extends", "same_method", "supports",
             "contradicts", "compares", "same_topic", "duplicate", "other"]
EXPLICIT = ("imports", "links_to", "mentions")  # reasons that are stated in the files themselves
STRUCTURAL = ("imports", "links_to")  # never dropped by the judge
GENERIC_NAMES = {"readme.md", "__init__.py", "index.md", "index.html", "main.py", "setup.py", "utils.py",
                 "config.py", "config.yaml", "config.json", "requirements.txt", "license", "makefile"}
QUOTE_CHARS = 300
EXCERPT_CHARS = 1500
RERANK_CHARS = 1200

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


def snippet(text: str, needle: str) -> str:
    i = text.find(needle)
    if i < 0:
        return text[:QUOTE_CHARS]
    s = max(0, i - QUOTE_CHARS // 2)
    return " ".join(text[s:s + QUOTE_CHARS].split())


def norm(s: str) -> str:
    return " ".join(s.split())


# ---- candidates ---------------------------------------------------------------------------------

def module_name(path: str) -> str:
    mod = path[:-3].replace("/", ".")
    return mod[:-len(".__init__")] if mod.endswith(".__init__") else mod


def resolve_import(src_path: str, target: str, modules: dict) -> str | None:
    level = len(target) - len(target.lstrip("."))
    name = target.lstrip(".")
    if level:
        pkg = module_name(src_path).split(".")
        if not src_path.endswith("__init__.py"):
            pkg = pkg[:-1]
        base = pkg[:len(pkg) - (level - 1)] if level > 1 else pkg
        return modules.get(".".join(base + ([name] if name else []))) if name else None
    if name in modules:
        return modules[name]
    hits = [m for m in modules if m.endswith("." + name)]  # src layouts and scripts run from a subfolder
    return modules[hits[0]] if len(hits) == 1 else None


def resolve_link(src_path: str, target: str, by_path: dict) -> str | None:
    t = urllib.parse.unquote(target.split("#")[0].split("?")[0])
    if not t or re.match(r"^[a-zA-Z][\w+.-]*:", t):  # empty, URL, mailto:
        return None
    cand = t.lstrip("/") if t.startswith("/") else posixpath.normpath(posixpath.join(posixpath.dirname(src_path), t))
    return by_path.get(cand) or by_path.get(posixpath.normpath(t))


def reference_candidates(record: Record):
    """Yield (source id, target id, reason, chunk id, quote) for imports, links and file-name mentions."""
    files = record.files
    by_path = {f.path: f.id for f in files}
    modules = {module_name(f.path): f.id for f in files if f.type == "python"}
    by_stem: dict[str, list[str]] = {}
    for f in files:
        by_stem.setdefault(posixpath.splitext(posixpath.basename(f.path))[0].lower(), []).append(f.id)
        by_stem.setdefault(posixpath.basename(f.path).lower(), []).append(f.id)
    for f in files:
        for ref in f.refs:
            if ref.kind == "import":
                tgt, reason = resolve_import(f.path, ref.target, modules), "imports"
            elif ref.kind == "link":
                tgt, reason = resolve_link(f.path, ref.target, by_path), "links_to"
            else:
                hits = by_stem.get(ref.target.lower(), [])
                tgt, reason = (hits[0] if len(hits) == 1 else None), "links_to"
            if tgt and tgt != f.id:
                yield f.id, tgt, reason, ref.chunk_id, snippet(record.chunk_by_id[ref.chunk_id].text, ref.target)

    # file-name mentions in any text chunk
    base_count = Counter(posixpath.basename(f.path).lower() for f in files)
    pattern_to_id = {}
    for f in files:
        base = posixpath.basename(f.path)
        if len(f.path) >= 5:
            pattern_to_id[f.path] = f.id
        if len(base) >= 5 and "." in base and base.lower() not in GENERIC_NAMES and base_count[base.lower()] == 1:
            pattern_to_id.setdefault(base, f.id)
    if not pattern_to_id:
        return
    alts = "|".join(re.escape(p) for p in sorted(pattern_to_id, key=len, reverse=True))
    rx = re.compile(rf"(?<![A-Za-z0-9_.\-])(?:{alts})(?![A-Za-z0-9_])")
    seen = set()
    for c in record.chunks:
        if c.kind == "path":
            continue
        for m in rx.finditer(c.text):
            tgt = pattern_to_id[m.group(0)]
            if tgt != c.file_id and (c.file_id, tgt) not in seen:
                seen.add((c.file_id, tgt))
                yield c.file_id, tgt, "mentions", c.id, snippet(c.text, m.group(0))


def similarity_candidates(record: Record, group_of: dict, cfg: Config):
    """Yield (i, j, cosine) file index pairs: top-k inside the group, the best one across groups."""
    textual = [i for i, f in enumerate(record.files)
               if any(record.chunk_by_id[c].kind != "path" for c in f.chunk_ids)]
    if len(textual) < 2:
        return
    e = record.file_emb[textual]
    sim = e @ e.T
    np.fill_diagonal(sim, -1.0)
    upper = sim[np.triu_indices(len(textual), 1)]
    t_in, t_cross = np.percentile(upper, cfg.sim_pct), np.percentile(upper, cfg.sim_cross_pct)
    groups = [group_of.get(record.files[i].id) for i in textual]
    for a in range(len(textual)):
        order = np.argsort(-sim[a])
        same = [b for b in order if groups[b] is not None and groups[b] == groups[a]][:cfg.k_within]
        for b in same:
            if sim[a, b] >= t_in:
                yield textual[a], textual[b], float(sim[a, b])
        other = next((b for b in order if groups[b] != groups[a] or groups[a] is None), None)
        if other is not None and sim[a, other] >= t_cross:
            yield textual[a], textual[other], float(sim[a, other])


# ---- evidence -----------------------------------------------------------------------------------

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


# ---- judgment -----------------------------------------------------------------------------------

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


# ---- stage entry --------------------------------------------------------------------------------

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
