"""Ground truth for relation graphs: the file format read by evaluation and the virtual-user simulation.

A ground-truth file (benchmark/gt/<project>/gt.json) lists judged file pairs by path:

- edges: related pairs with a relation type from schema.RELATIONS. `required` edges count toward recall;
  optional ones (a weak but real relation) are never penalized when predicted and never required.
- negatives: pairs a person judged unrelated.

Pairs in neither list are unjudged. Evaluation leaves them out of precision and reports how many predictions
were unjudged, a locally closed world as in Text2KGBench (Mihindukulasooriya et al., ISWC 2023).

Edges come in two layers: explicit (what the files state themselves: imports, links, file-name mentions) and
semantic (judged on a pool of candidate pairs, as in TREC pooling). `groups` records how a person would chunk
the files, and `levels` the default hierarchy of the whole folder (top / middle / bottom, every file once). How the
benchmark's ground truth was built is described in benchmark/README.md.

Preference ground truth pairs a user's preference (the input, one sentence) with the output it should produce, one
file per kind next to gt.json:
- purposes.json, links: a purpose -> the ground-truth links it needs (and the ones it can take or leave).
  A link preference changes only those links: needed links become key links, so `promote` lists the weak ones it
  raises; every other link keeps its default state. purpose_view applies this for the same metrics.
- groupings.json, groups: how the user wants the files grouped -> every file in one group.
- levels.json, levels: what the user wants higher or lower -> the level of every file.
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
    levels: dict = field(default_factory=dict)  # {"top", "middle", "bottom": [paths]}: the folder's default hierarchy

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
                   unsure=d.get("unsure", []), meta=d.get("meta", {}), groups=d.get("groups", []),
                   levels=d.get("levels", {}))


# ---- preference ground truth --------------------------------------------------------------------
# groupings.json and levels.json: {"project", "preferences": [{"id", "corrections", <output>}]}. The input is the
# corrections (structured viewer edits, below), the output is what the map should show after them.
# purposes.json: {"project", "purposes": [{"id", "base", "text", <output>, "corrections"}]}. `text` is the purpose
# (the pipeline's --purpose input, the user's intent); the corrections are the link edits it implies.
# Every record also has "corrections" (below): the viewer edits that give the output from the default ground truth.
# purposes.json, key "purposes": also "base" (the side the purpose starts from: code | docs), output "needed" and
#   "optional" ([[a, b]] ground-truth pairs; the needed links become key links, every other link keeps its default
#   state) and, for the teammate's hand labels, "notes" {pair_key: why}.
# groupings.json, key "preferences": output "groups" [{"name", "members"}], every project file once.
# levels.json, key "preferences": output "levels" {"top", "middle", "bottom": [paths]}, every project file once.
LEVEL_VALUE = {"top": 3, "middle": 2, "bottom": 1}
PREFERENCE_FILES = {"purposes": ("purposes.json", "purposes"), "groupings": ("groupings.json", "preferences"),
                    "levels": ("levels.json", "preferences")}


def load_preferences(gt_dir: Path, kind: str) -> list[dict]:
    """One kind of preference ground truth (purposes | groupings | levels) next to a gt.json, or []."""
    name, key = PREFERENCE_FILES[kind]
    path = Path(gt_dir) / name
    return json.loads(path.read_text(encoding="utf-8"))[key] if path.exists() else []


def load_purposes(gt_dir: Path) -> list[dict]:
    """The purposes (link preferences) defined next to a gt.json, or [] when the project has none."""
    return load_preferences(gt_dir, "purposes")


def project_files(gt: GroundTruth) -> set[str]:
    return {m for g in gt.groups for m in g["members"]}


def level_map(levels: dict) -> dict[str, int]:
    """{"top", "middle", "bottom": [paths]} -> path -> 3 | 2 | 1."""
    return {m: LEVEL_VALUE[k] for k in LEVEL_VALUE for m in levels.get(k, [])}


def check_levels(files: set[str], levels: dict, who: str) -> list[str]:
    """Every project file on exactly one of the three levels."""
    placed = [m for k in LEVEL_VALUE for m in levels.get(k, [])]
    return ([f"{who}: unknown level {k!r}" for k in sorted(set(levels) - LEVEL_VALUE.keys())]
            + [f"{who}: {m} is on more than one level" for m in sorted({m for m in placed if placed.count(m) > 1})]
            + [f"{who}: {m} is not a project file" for m in sorted(set(placed) - files)]
            + [f"{who}: {m} has no level" for m in sorted(files - set(placed))])


def check_groups(files: set[str], groups: list[dict], who: str) -> list[str]:
    """Every project file in exactly one group, group names distinct."""
    members = [m for g in groups for m in g["members"]]
    names = [g["name"] for g in groups]
    return ([f"{who}: group name repeated: {n}" for n in sorted({n for n in names if names.count(n) > 1})]
            + [f"{who}: {m} is in more than one group" for m in sorted({m for m in members if members.count(m) > 1})]
            + [f"{who}: {m} is not a project file" for m in sorted(set(members) - files)]
            + [f"{who}: {m} is in no group" for m in sorted(files - set(members))])


def check_ids(prefs: list[dict], text: bool = False) -> list[str]:
    """Ids present and distinct; with text=True (purposes) also a non-empty text."""
    problems, ids = [], set()
    for p in prefs:
        pid = p.get("id")
        if not pid or pid in ids:
            problems.append(f"preference id missing or repeated: {pid!r}")
        ids.add(pid)
        if text and not p.get("text", "").strip():
            problems.append(f"{pid}: empty text")
    return problems


def check_purposes(gt: GroundTruth, purposes: list[dict]) -> list[str]:
    """Problems in a project's purposes: unknown pairs, a pair both needed and optional, corrections that do not give
    the purpose's links, bad ids or text."""
    edges, problems = gt.edge_by_key, check_ids(purposes, text=True)
    for p in purposes:
        pid = p.get("id")
        needed = {pair_key(a, b) for a, b in p.get("needed", [])}
        optional = {pair_key(a, b) for a, b in p.get("optional", [])}
        problems += [f"{pid}: {k} is not a ground-truth edge" for k in sorted((needed | optional) - edges.keys())]
        problems += [f"{pid}: {k} is both needed and optional" for k in sorted(needed & optional)]
    if not problems:
        problems += check_corrections(gt, "purposes", purposes)
    return problems


def check_groupings(gt: GroundTruth, prefs: list[dict]) -> list[str]:
    files = project_files(gt)
    problems = check_ids(prefs) + [x for p in prefs for x in check_groups(files, p.get("groups", []), str(p.get("id")))]
    return problems or check_corrections(gt, "groupings", prefs)


def check_level_prefs(gt: GroundTruth, prefs: list[dict]) -> list[str]:
    files = project_files(gt)
    problems = check_ids(prefs) + [x for p in prefs for x in check_levels(files, p.get("levels", {}), str(p.get("id")))]
    problems += check_levels(files, gt.levels, "default levels") if gt.levels else []
    return problems or check_corrections(gt, "levels", prefs)


def purpose_view(gt: GroundTruth, purpose: dict) -> GroundTruth:
    """Ground truth with one link preference applied. A preference changes only the links it is about: its needed
    links become key (required) links, weak ones included; every other link keeps its default state, and nothing is
    dropped. The same shape as feedback_sim.persona_view, so every metric applies."""
    needed = {pair_key(a, b) for a, b in purpose.get("needed", [])}
    return replace(gt, edges=[replace(e, required=e.required or e.key in needed) for e in gt.edges])


# ---- structured corrections ---------------------------------------------------------------------
# Each preference also holds "corrections": the edits a user makes in the viewer to turn the default ground truth into
# the preference's output (the input format chosen at the 2026-11-26 meeting; the sentence stays as the user's intent).
# - grouping: {"op": "move", "file", "to"} / {"op": "add_group", "name"} / {"op": "delete_group", "name"} (an empty group)
# - link: {"op": "add", "a", "b"} (a weak link becomes a key link) / {"op": "delete", "a", "b"} /
#   {"op": "change", "a", "b", "to": [a2, b2]}. Only "add" occurs so far: link preferences raise links, never drop them.
# - level: {"op": "set_level", "file", "importance": 3 | 2 | 1} (3 = top, 2 = middle, 1 = bottom)
# The apply_* functions replay them on the default; check_corrections verifies they give the preference's output.
IMPORTANCE_LEVEL = {v: k for k, v in LEVEL_VALUE.items()}


def partition(groups: list[dict]) -> frozenset:
    return frozenset(frozenset(g["members"]) for g in groups)


def grouping_corrections(default: list[dict], groups: list[dict]) -> list[dict]:
    """Few edits from the default groups to `groups`: each preference group continues the default group it shares the
    most files with (each default group once, the same name breaking ties); the others are added; files not already
    there move; emptied default groups are deleted."""
    home = {m: g["name"] for g in default for m in g["members"]}
    overlaps = sorted(((len(set(p["members"]) & set(d["members"])), p["name"] == d["name"], -i, -j)
                       for i, p in enumerate(groups) for j, d in enumerate(default)), reverse=True)
    keep, used = {}, set()
    for size, _, i, j in overlaps:  # most shared files first; on a tie the group that kept its name
        if size and -i not in keep and -j not in used:
            keep[-i] = default[-j]["name"]
            used.add(-j)
    taken = {d["name"] for d in default}
    name, ops = {}, []
    for i, g in enumerate(groups):
        if i in keep:
            name[i] = keep[i]
        else:
            name[i] = g["name"] if g["name"] not in taken else f"{g['name']} (새 그룹)"
            taken.add(name[i])
            ops.append({"op": "add_group", "name": name[i]})
    ops += [{"op": "move", "file": m, "to": name[i]} for i, g in enumerate(groups) for m in sorted(g["members"])
            if home.get(m) != name[i]]
    return ops + [{"op": "delete_group", "name": d["name"]} for j, d in enumerate(default) if j not in used]


def apply_grouping(default: list[dict], ops: list[dict]) -> list[dict]:
    groups = {g["name"]: list(g["members"]) for g in default}
    for o in ops:
        if o["op"] == "add_group":
            if o["name"] in groups:
                raise ValueError(f"add_group: {o['name']} exists")
            groups[o["name"]] = []
        elif o["op"] == "move":
            if o["to"] not in groups:
                raise ValueError(f"move: no group {o['to']}")
            for members in groups.values():
                if o["file"] in members:
                    members.remove(o["file"])
            groups[o["to"]].append(o["file"])
        elif o["op"] == "delete_group":
            if groups.get(o["name"]) is None or groups[o["name"]]:
                raise ValueError(f"delete_group: {o['name']} is missing or not empty")
            del groups[o["name"]]
        else:
            raise ValueError(f"unknown grouping op {o['op']!r}")
    return [{"name": n, "members": sorted(ms)} for n, ms in groups.items()]


def link_corrections(gt: GroundTruth, needed: list[list[str]]) -> list[dict]:
    """A link preference raises the needed links that are weak by default; nothing else changes."""
    edges = gt.edge_by_key
    return [{"op": "add", "a": a, "b": b} for a, b in needed if not edges[pair_key(a, b)].required]


def apply_links(gt: GroundTruth, ops: list[dict]) -> GroundTruth:
    edges = dict(gt.edge_by_key)
    for o in ops:
        k = pair_key(o["a"], o["b"])
        if k not in edges:
            raise ValueError(f"{o['op']}: {k} is not a ground-truth edge")
        if o["op"] == "add":
            edges[k] = replace(edges[k], required=True)
        elif o["op"] == "delete":
            del edges[k]
        elif o["op"] == "change":
            a2, b2 = o["to"]
            edges.pop(k)
            edges[pair_key(a2, b2)] = replace(gt.edge_by_key[k], a=a2, b=b2, required=True)
        else:
            raise ValueError(f"unknown link op {o['op']!r}")
    return replace(gt, edges=list(edges.values()))


def level_corrections(default: dict, levels: dict) -> list[dict]:
    before, after = level_map(default), level_map(levels)
    return [{"op": "set_level", "file": f, "importance": after[f]} for f in sorted(after) if after[f] != before.get(f)]


def apply_levels(default: dict, ops: list[dict]) -> dict:
    value = level_map(default)
    for o in ops:
        if o["op"] != "set_level" or o["importance"] not in IMPORTANCE_LEVEL or o["file"] not in value:
            raise ValueError(f"bad level correction {o}")
        value[o["file"]] = o["importance"]
    return {k: sorted(f for f, v in value.items() if v == LEVEL_VALUE[k]) for k in LEVEL_VALUE}


def check_corrections(gt: GroundTruth, kind: str, prefs: list[dict]) -> list[str]:
    """Each preference's corrections, replayed on the default ground truth, give exactly its output."""
    problems = []
    for p in prefs:
        pid, ops = p.get("id"), p.get("corrections")
        if ops is None:
            problems.append(f"{pid}: no corrections")
            continue
        try:
            if kind == "groupings":
                ok = partition(apply_grouping(gt.groups, ops)) == partition(p["groups"])
            elif kind == "levels":
                ok = level_map(apply_levels(gt.levels, ops)) == level_map(p["levels"])
            else:
                weak = {e.key for e in gt.edges if not e.required}
                ok = (all(pair_key(o["a"], o["b"]) in weak for o in ops if o["op"] == "add")
                      and {e.key for e in apply_links(gt, ops).edges if e.required}
                      == {e.key for e in purpose_view(gt, p).edges if e.required})
        except (ValueError, KeyError) as err:
            problems.append(f"{pid}: corrections do not apply: {err}")
            continue
        if not ok:
            problems.append(f"{pid}: corrections do not give the preference's output")
    return problems


def describe_corrections(ops: list[dict], limit: int = 4) -> str:
    """Short Korean summary of corrections, for tables and captions."""
    name = lambda f: f.rsplit("/", 1)[-1]  # noqa: E731
    words = []
    for o in ops:
        if o["op"] == "move":
            words.append(f"{name(o['file'])} → {o['to']}")
        elif o["op"] == "add_group":
            words.append(f"새 그룹 '{o['name']}'")
        elif o["op"] == "delete_group":
            words.append(f"그룹 '{o['name']}' 삭제")
        elif o["op"] == "set_level":
            words.append(f"{name(o['file'])} 중요도 {o['importance']}")
        elif o["op"] == "add":
            words.append(f"{name(o['a'])}–{name(o['b'])} 핵심으로")
        elif o["op"] == "delete":
            words.append(f"{name(o['a'])}–{name(o['b'])} 삭제")
        elif o["op"] == "change":
            words.append(f"{name(o['a'])}–{name(o['b'])} 변경")
    if not words:
        return "교정 없음"
    return " · ".join(words[:limit]) + (f" 외 {len(words) - limit}개" if len(words) > limit else "")
