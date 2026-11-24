"""Ground truth for relation graphs: the file format read by evaluation and the virtual-user simulation.

A ground-truth file (benchmark/gt/<project>/gt.json) lists judged file pairs by path:

- edges: related pairs with a relation type from schema.RELATIONS. `required` edges count toward recall;
  optional ones (a weak but real relation) are never penalized when predicted and never required.
- negatives: pairs a person judged unrelated.

Pairs in neither list are unjudged. Evaluation leaves them out of precision and reports how many predictions
were unjudged, a locally closed world as in Text2KGBench (Mihindukulasooriya et al., ISWC 2023).

Edges come in two layers: explicit (what the files state themselves: imports, links, file-name mentions) and
semantic (judged on a pool of candidate pairs, as in TREC pooling). `groups` records how a person would chunk
the files. How the benchmark's ground truth was built is described in benchmark/README.md.

A project may also have purposes (benchmark/gt/<project>/purposes.json, optional): a user's purpose in words
(the text given to `projectwiki build --purpose`) with the ground-truth pairs it needs and the ones it can take
or leave. purpose_view turns the ground truth into the graph that purpose wants, for the same metrics.
"""
from __future__ import annotations

import json
import posixpath
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

# Twelve relations folded into four classes for a lenient relation-type score.
COARSE = {"implements": "code", "uses": "code", "produces": "code", "describes": "doc",
          "extends": "research", "same_method": "research", "supports": "research", "contradicts": "research",
          "compares": "research", "same_topic": "topic", "duplicate": "topic", "other": "topic"}
SYMMETRIC = {"same_method", "same_topic", "compares", "duplicate", "contradicts", "other"}

CODE_EXT = {".py", ".c", ".h", ".cc", ".cpp", ".cu", ".cuh", ".sh", ".bat", ".ps1", ".js", ".ts", ".java"}
CONFIG_EXT = {".yaml", ".yml", ".json", ".toml", ".cfg", ".ini", ".txt", ".css"}
DOC_EXT = {".md", ".rst", ".tex", ".html", ".sty", ".bst"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}


def category(path: str) -> str:
    """code | notebook | config | doc | paper | image | other, from the file name alone."""
    name = posixpath.basename(path).lower()
    ext = posixpath.splitext(name)[1]
    if name == "makefile" or ext in CODE_EXT:
        return "code"
    if ext == ".ipynb":
        return "notebook"
    if ext == ".pdf":
        return "paper"
    if ext in IMAGE_EXT:
        return "image"
    if ext in DOC_EXT:
        return "doc"
    if ext in CONFIG_EXT:
        return "config"
    return "other"


def pair_key(a: str, b: str) -> str:
    return f"{a}|{b}" if a < b else f"{b}|{a}"


@dataclass
class GTEdge:
    a: str
    b: str
    relation: str
    also: list[str] = field(default_factory=list)  # other relation types accepted for this pair
    direction: str = "a_to_b"  # a_to_b reads "a <relation> b"; both; unknown when not judged
    required: bool = True
    layer: str = "semantic"  # explicit | semantic
    evidence: dict = field(default_factory=dict)  # {"file": path, "span": text}
    source: str = "manual"  # static-analysis | manual | designed (mock projects)
    note: str = ""
    personas: list[str] = field(default_factory=list)  # code | docs when designed; empty: decided by file type

    @property
    def key(self) -> str:
        return pair_key(self.a, self.b)

    def accepts(self, relation: str) -> bool:
        return relation == self.relation or relation in self.also


@dataclass
class GroundTruth:
    project: str
    edges: list[GTEdge] = field(default_factory=list)
    negatives: list[dict] = field(default_factory=list)  # {"a", "b", "source", "note"}
    unsure: list[dict] = field(default_factory=list)  # judged but undecided; left out like unjudged pairs
    meta: dict = field(default_factory=dict)
    groups: list[dict] = field(default_factory=list)  # {"name", "members": [paths]}: how a person chunks the files

    @property
    def edge_by_key(self) -> dict[str, GTEdge]:
        return {e.key: e for e in self.edges}

    @property
    def negative_keys(self) -> set[str]:
        return {pair_key(n["a"], n["b"]) for n in self.negatives}

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=1), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> GroundTruth:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(project=d["project"], edges=[GTEdge(**e) for e in d["edges"]], negatives=d.get("negatives", []),
                   unsure=d.get("unsure", []), meta=d.get("meta", {}), groups=d.get("groups", []))


# ---- purposes ------------------------------------------------------------------------------------
# purposes.json: {"project", "purposes": [{"id", "base", "text", "needed": [[a, b]], "optional": [[a, b]],
# "notes": {pair_key: why}}], "review_log": [...]}. `base` is the persona the tags started from (code | docs).
# needed: the purpose wants the link shown. optional: shown or hidden, both fine. Every other pair: not needed.

def load_purposes(gt_dir: Path) -> list[dict]:
    """The purposes defined next to a gt.json, or [] when the project has none."""
    path = Path(gt_dir) / "purposes.json"
    return json.loads(path.read_text(encoding="utf-8"))["purposes"] if path.exists() else []


def check_purposes(gt: GroundTruth, purposes: list[dict]) -> list[str]:
    """Problems in a project's purposes: unknown pairs, a pair both needed and optional, bad ids or text."""
    edges, problems, ids = gt.edge_by_key, [], set()
    for p in purposes:
        if not p.get("id") or p["id"] in ids:
            problems.append(f"purpose id missing or repeated: {p.get('id')!r}")
        ids.add(p.get("id"))
        if not p.get("text", "").strip():
            problems.append(f"{p.get('id')}: empty text")
        needed = {pair_key(a, b) for a, b in p.get("needed", [])}
        optional = {pair_key(a, b) for a, b in p.get("optional", [])}
        problems += [f"{p['id']}: {k} is not a ground-truth edge" for k in sorted((needed | optional) - edges.keys())]
        problems += [f"{p['id']}: {k} is both needed and optional" for k in sorted(needed & optional)]
    return problems


def purpose_view(gt: GroundTruth, purpose: dict) -> GroundTruth:
    """Ground truth as one purpose sees it: needed edges are required, optional ones are never penalized,
    every other edge becomes a negative. The same shape as feedback_sim.persona_view, so every metric applies."""
    needed = {pair_key(a, b) for a, b in purpose.get("needed", [])}
    optional = {pair_key(a, b) for a, b in purpose.get("optional", [])}
    keep = [replace(e, required=e.key in needed) for e in gt.edges if e.key in needed | optional]
    off = [{"a": e.a, "b": e.b, "source": "purpose", "note": f"not needed for {purpose['id']}"}
           for e in gt.edges if e.key not in needed | optional]
    return replace(gt, edges=keep, negatives=gt.negatives + off)
