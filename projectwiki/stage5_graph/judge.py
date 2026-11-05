"""Stage 5, step 3: Claude names each relation, its direction and a label, marks it direct or inferred,
and quotes both sides; quotes that are not found verbatim in the excerpts are discarded."""
from __future__ import annotations

import logging

from ..config import Config
from ..models import Claude, obj_schema
from ..schema import EXPLICIT, RELATIONS, STRUCTURAL, Edge, Evidence
from ..stage3_record import Record

log = logging.getLogger(__name__)
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
