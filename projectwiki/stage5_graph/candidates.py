"""Stage 5, step 1: candidate edges.

Explicit references (imports, Markdown links, wikilinks, file-name mentions) and bge-m3 similarity
(top-k inside each group, one strong neighbour across groups).
"""
from __future__ import annotations

import posixpath
import re
import urllib.parse
from collections import Counter

import numpy as np

from ..config import Config
from ..stage3_record import Record
GENERIC_NAMES = {"readme.md", "__init__.py", "index.md", "index.html", "main.py", "setup.py", "utils.py",
                 "config.py", "config.yaml", "config.json", "requirements.txt", "license", "makefile"}
QUOTE_CHARS = 300


def snippet(text: str, needle: str) -> str:
    i = text.find(needle)
    if i < 0:
        return text[:QUOTE_CHARS]
    s = max(0, i - QUOTE_CHARS // 2)
    return " ".join(text[s:s + QUOTE_CHARS].split())


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
