"""Data contracts shared by every pipeline stage."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field

# Relation types the structure-generation judge (models/structure.py) may assign.
RELATIONS = ["implements", "describes", "uses", "produces", "extends", "same_method", "supports",
             "contradicts", "compares", "same_topic", "duplicate", "other"]
EXPLICIT = ("imports", "links_to", "mentions")  # candidate reasons stated in the files themselves
STRUCTURAL = ("imports", "links_to")  # facts: only the user can remove them

# Edge statuses the viewer shows by default; the others are kept for inspection.
VISIBLE_STATUS = ("proposed", "confirmed")

FEEDBACK_TYPES = {
    "edge_add": "빠진 연결 추가",
    "edge_wrong": "잘못된 연결 (사실 오류)",
    "edge_irrelevant": "관련은 있지만 목적상 불필요",
    "edge_confirm": "맞는 연결 (승인)",
    "node_move": "다른 그룹으로 이동",
    "node_ungroup": "그룹에서 빼기",
}


def edge_key(a: str, b: str) -> str:
    """One edge per unordered file pair."""
    return f"{a}|{b}" if a < b else f"{b}|{a}"


@dataclass
class Ref:
    kind: str  # import | link | wikilink
    target: str
    chunk_id: str


@dataclass
class Chunk:
    id: str
    file_id: str
    kind: str  # page | section | module | function | class | cell | text | path
    locator: str  # "p.3", "Method > Loss", "def train (L10-L42)", "cell 4 (code)"
    text: str


@dataclass
class FileRecord:
    id: str
    path: str  # posix path relative to the project root
    type: str  # pdf | markdown | python | notebook | text | image | media | other
    sha256: str
    size: int
    title: str
    chunk_ids: list[str] = field(default_factory=list)
    refs: list[Ref] = field(default_factory=list)
    summary: str = ""  # Claude summary (srcs/enrich.py)
    role: str = ""  # LLM role label such as "training script"

    @classmethod
    def from_dict(cls, d: dict) -> FileRecord:
        return cls(**{**d, "refs": [Ref(**r) for r in d["refs"]]})


@dataclass
class Group:
    id: str
    name: str
    members: list[str] = field(default_factory=list)
    origin: str = "ai"  # ai | user
    description: str = ""


@dataclass
class Evidence:
    chunk_id: str
    file_id: str
    locator: str
    quote: str


@dataclass
class Edge:
    id: str
    source: str
    target: str
    relation: str
    reason: str  # why the candidate exists: imports | links_to | mentions | similar | user
    direct: bool  # stated in the files (reference or verified quote) vs inferred
    score: float
    label: str = ""
    evidence: list[Evidence] = field(default_factory=list)
    origin: str = "ai"  # ai | user
    # proposed | confirmed | removed_wrong | removed_irrelevant | removed_by_corrector
    # | removed_low_score | llm_rejected
    status: str = "proposed"
    correction: str = ""  # why the preference method (models/preference.py) changed this edge

    @classmethod
    def from_dict(cls, d: dict) -> Edge:
        return cls(**{**d, "evidence": [Evidence(**v) for v in d["evidence"]]})


@dataclass
class Node:
    id: str
    path: str
    type: str
    title: str
    group: str | None
    role: str = ""
    summary: str = ""


@dataclass
class Graph:
    nodes: list[Node]
    groups: list[Group]
    edges: list[Edge]

    def to_dict(self) -> dict:
        return asdict(self)

    def revision(self) -> str:
        data = json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, d: dict) -> Graph:
        return cls(nodes=[Node(**n) for n in d["nodes"]],
                   groups=[Group(**g) for g in d["groups"]],
                   edges=[Edge.from_dict(e) for e in d["edges"]])


@dataclass
class Preferences:
    """User preference inputs for the clustering stage. The baseline clusterer ignores them."""
    purpose: str = ""
    anchors: list[str] = field(default_factory=list)  # files the user marked as central (paths)
    guide: dict[str, str] = field(default_factory=dict)  # multiple-choice answers on how to organize
    pairs: list[dict] = field(default_factory=list)  # {"a": path, "b": path, "score": 1-5}


@dataclass
class FeedbackEvent:
    """One user correction. File references are file ids or project-relative paths."""
    type: str  # a key of FEEDBACK_TYPES
    source: str | None = None
    target: str | None = None
    node: str | None = None
    group: str | None = None  # group id, or a new group name for node_move
    relation: str | None = None  # user's relation name for edge_add
    note: str = ""
    ts: str = ""
