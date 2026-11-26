"""Comparison graphs for task 1, made by rule (no hand edits), in the pipeline's Graph format.

- obsidian: only references written in the files (imports, Markdown links / wikilinks, file-name mentions),
  pointing from the file that refers to the file it refers to. No groups.
- similar:  only content similarity (TF-IDF cosine, each file's 2 nearest neighbours above the 75th percentile).
  No direction, no groups.

Both get groups and one-line link explanations by rule too (folders for obsidian, shared-word clusters for similar).
Both are the two kinds of candidate edges the pipeline itself starts from (projectwiki/srcs/candidates.py:
reason imports / links_to / mentions vs similar). Two ways to make them:

  python user_study_v2/make_baselines.py mock_plant_fewshot
      standalone rules that mirror candidates.py (no extra packages; PDFs are read with zlib)
  python user_study_v2/make_baselines.py mock_plant_fewshot --from-graph runs/x/graph.json
      filter a real pipeline graph (e.g. `projectwiki build ... --no-llm --encoder tfidf`) by edge reason

Writes user_study_v2/data/<project>/graphs/{obsidian,similar}.json.
"""
from __future__ import annotations

import argparse
import json
import math
import posixpath
import re
import zlib
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
GENERIC_NAMES = {"readme.md", "__init__.py", "index.md", "index.html", "main.py", "setup.py", "utils.py",
                 "config.py", "config.yaml", "config.json", "requirements.txt", "license", "makefile"}
EXPLICIT = ("imports", "links_to", "mentions")
TYPE = {".py": "python", ".md": "markdown", ".pdf": "pdf", ".ipynb": "notebook", ".png": "image", ".jpg": "image"}
QUOTE = 300


def file_type(path: str) -> str:
    return TYPE.get(posixpath.splitext(path)[1].lower(), "text")


def pdf_text(data: bytes) -> str:
    """Text of a simple PDF: inflate every stream and keep the strings shown with Tj / TJ."""
    out = []
    for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", data, re.S):
        try:
            s = zlib.decompress(m.group(1))
        except zlib.error:
            continue
        for lit, hexs in re.findall(rb"\(((?:\\.|[^\\)])*)\)|<([0-9a-fA-F\s]+)>", s):
            if hexs:
                out.append(bytes.fromhex(hexs.decode().replace(" ", "").replace("\n", "")).decode("latin-1"))
            else:
                out.append(lit.replace(rb"\(", b"(").replace(rb"\)", b")").replace(rb"\\", b"\\").decode("latin-1"))
        out.append("\n")
    return re.sub(r"[ \t]+", " ", " ".join(out))


def read_files(project: Path) -> dict[str, str]:
    texts = {}
    for p in sorted(project.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(project).as_posix()
        t = file_type(rel)
        if t == "image":
            texts[rel] = ""
        elif t == "pdf":
            texts[rel] = pdf_text(p.read_bytes())
        else:
            texts[rel] = p.read_text(encoding="utf-8", errors="replace")
    return texts


def snippet(text: str, needle: str) -> str:
    i = text.find(needle)
    s = max(0, i - QUOTE // 2) if i >= 0 else 0
    return " ".join(text[s:s + QUOTE].split())


def module_name(path: str) -> str:
    mod = path[:-3].replace("/", ".")
    return mod[:-len(".__init__")] if mod.endswith(".__init__") else mod


def references(texts: dict[str, str]):
    """(source, target, reason, quote): imports, links and file-name mentions, as in candidates.py."""
    paths = list(texts)
    modules = {module_name(p): p for p in paths if p.endswith(".py")}

    def resolve_import(name: str) -> str | None:
        name = name.lstrip(".")
        if name in modules:
            return modules[name]
        hits = [m for m in modules if m.endswith("." + name)]
        return modules[hits[0]] if len(hits) == 1 else None

    for src, text in texts.items():
        if src.endswith(".py"):
            for m in re.finditer(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", text, re.M):
                tgt = resolve_import(m.group(1) or m.group(2))
                if tgt and tgt != src:
                    yield src, tgt, "imports", snippet(text, m.group(0).strip())
        if src.endswith((".md", ".html")):
            for m in re.finditer(r"\]\(([^)\s]+)\)|\[\[([^\]|#]+)|(?:src|href)=\"([^\"]+)\"", text):
                t = m.group(1) or m.group(2) or m.group(3)
                if re.match(r"^[a-zA-Z][\w+.-]*:", t):
                    continue
                cand = posixpath.normpath(posixpath.join(posixpath.dirname(src), t.split("#")[0]))
                if cand in texts and cand != src:
                    yield src, cand, "links_to", snippet(text, t)

    base_count = Counter(posixpath.basename(p).lower() for p in paths)
    pattern = {}
    for p in paths:
        b = posixpath.basename(p)
        if len(p) >= 5:
            pattern[p] = p
        if len(b) >= 5 and "." in b and b.lower() not in GENERIC_NAMES and base_count[b.lower()] == 1:
            pattern.setdefault(b, p)
    rx = re.compile(r"(?<![A-Za-z0-9_.\-])(?:" + "|".join(re.escape(k) for k in sorted(pattern, key=len, reverse=True))
                    + r")(?![A-Za-z0-9_])")
    for src, text in texts.items():
        for m in rx.finditer(text):
            tgt = pattern[m.group(0)]
            if tgt != src:
                yield src, tgt, "mentions", snippet(text, m.group(0))



STOP = set("""the and of to in a is for on with as by from def self return if this that are be it we our an at or not
none true false else elif import class print args str int float list dict len range use used using can will each per
md py csv png pdf yaml log http https www com""".split())


def tfidf(texts: dict[str, str]) -> dict[str, dict[str, float]]:
    docs = {p: [w for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]+|[가-힣]{2,}", t.lower()) if w not in STOP and len(w) > 2]
            for p, t in texts.items() if t.strip()}
    df = Counter(w for ws in docs.values() for w in set(ws))
    n = len(docs)
    vec = {}
    for p, ws in docs.items():
        tf = Counter(ws)
        v = {w: (1 + math.log(c)) * (math.log((1 + n) / (1 + df[w])) + 1) for w, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1
        vec[p] = {w: x / norm for w, x in v.items()}
    return vec


def cos(a: dict, b: dict) -> float:
    return sum(x * b.get(w, 0) for w, x in a.items())


def tfidf_neighbours(vec, k: int = 2, pct: float = 75):
    ps = list(vec)
    sim = {(a, b): cos(vec[a], vec[b]) for a in ps for b in ps if a != b}
    upper = sorted(sim[(a, b)] for i, a in enumerate(ps) for b in ps[i + 1:])
    thr = upper[int(len(upper) * pct / 100)]
    for a in ps:
        for b in sorted((b for b in ps if b != a), key=lambda b: -sim[(a, b)])[:k]:
            if sim[(a, b)] >= thr:
                yield a, b, round(sim[(a, b)], 4)


def top_words(v: dict, n: int) -> list[str]:
    return [w for w, _ in sorted(v.items(), key=lambda x: -x[1])[:n]]


def shared_words(a: dict, b: dict, n: int = 3) -> list[str]:
    return [w for w, _ in sorted(((w, x * b[w]) for w, x in a.items() if w in b), key=lambda x: -x[1])[:n]]


def clusters(vec, n_groups: int) -> list[list[str]]:
    """Average-link agglomerative clustering on TF-IDF cosine, merged until n_groups remain."""
    cl = [[p] for p in sorted(vec)]
    sim = lambda A, B: sum(cos(vec[a], vec[b]) for a in A for b in B) / (len(A) * len(B))  # noqa: E731
    while len(cl) > n_groups:
        i, j = max(((i, j) for i in range(len(cl)) for j in range(i + 1, len(cl))), key=lambda ij: sim(cl[ij[0]], cl[ij[1]]))
        cl[i] = cl[i] + cl[j]
        del cl[j]
    return sorted(cl, key=lambda c: -len(c))


def preview(text: str) -> str:
    """First heading or first meaningful line, as a note preview shows it."""
    for line in text.splitlines():
        t = line.strip().lstrip("#").strip().strip('"').strip()
        if len(t) >= 6 and not t.startswith(("import ", "from ", "---", "<", "%")):
            return t[:90] + ("…" if len(t) > 90 else "")
    return ""


def edge_key(a: str, b: str) -> str:
    return f"{a}|{b}" if a < b else f"{b}|{a}"


def edge(src, tgt, relation, reason, direct, score, quote="", label=""):
    return {"id": edge_key(src, tgt), "source": src, "target": tgt, "relation": relation, "reason": reason,
            "direct": direct, "score": score, "label": label,
            "evidence": [{"chunk_id": "", "file_id": src, "locator": "", "quote": quote}] if quote else [],
            "origin": "ai", "status": "proposed", "correction": ""}


REF_LABEL = {"imports": "{a}가 {b}를 import합니다.", "links_to": "{a}에 {b}로 가는 링크가 있습니다.",
             "mentions": "{a}에 {b}의 파일 이름이 적혀 있습니다."}


def obsidian_graph(paths, ref, texts):
    """Obsidian's graph view: links written in the notes; colour groups by folder (its usual path:folder groups)."""
    by_dir = {}
    for p in paths:
        by_dir.setdefault(p.split("/")[0] + "/" if "/" in p else "(맨 위 폴더)", []).append(p)
    groups = [{"id": f"o{i + 1}", "name": d, "members": m, "origin": "ai",
               "description": f"{d} 폴더에 있는 파일" if d.endswith("/") else "폴더에 들어 있지 않은 파일"}
              for i, (d, m) in enumerate(sorted(by_dir.items(), key=lambda x: (-len(x[1]), x[0])))]
    gid = {m: g["id"] for g in groups for m in g["members"]}
    for e in ref.values():
        e["label"] = REF_LABEL[e["reason"]].format(a=posixpath.basename(e["source"]), b=posixpath.basename(e["target"]))
    return groups, gid


def similar_graph(paths, sim, texts, vec):
    """A 'related documents' view: files grouped by shared vocabulary, named by their most typical words."""
    textual = [p for p in paths if p in vec]
    groups = []
    for i, c in enumerate(clusters(vec, max(4, round(len(textual) / 4)))):
        cen = Counter()
        for p in c:
            cen.update(vec[p])
        words = top_words(cen, 5)
        groups.append({"id": f"s{i + 1}", "name": " · ".join(words[:3]), "members": sorted(c), "origin": "ai",
                       "description": "이 파일들에 자주 나오는 단어: " + ", ".join(words)})
    rest = [p for p in paths if p not in vec]
    if rest:
        groups.append({"id": f"s{len(groups) + 1}", "name": "글이 없는 파일", "members": rest, "origin": "ai",
                       "description": "그림처럼 글 내용이 없어 단어로 비교할 수 없는 파일"})
    gid = {m: g["id"] for g in groups for m in g["members"]}
    for e in sim.values():
        w = shared_words(vec[e["source"]], vec[e["target"]])
        e["label"] = f"두 파일에 함께 자주 나오는 단어: {', '.join(w)} (유사도 {e['score']:.2f})"
    return groups, gid


def graph(paths, edges, groups, gid, texts, method, source, made_from):
    nodes = [{"id": p, "path": p, "type": file_type(p), "title": posixpath.basename(p), "group": gid.get(p),
              "role": "", "summary": preview(texts.get(p, ""))} for p in paths]
    return {"meta": {"source": source, "method": method, "made_from": made_from}, "nodes": nodes, "groups": groups,
            "edges": list(edges.values())}


def from_rules(texts, vec):
    ref, sim = {}, {}
    for s, t, reason, q in references(texts):  # first reference per file pair wins, as in the pipeline
        ref.setdefault(edge_key(s, t), edge(s, t, reason, reason, True, 1.0, q))
    for a, b, c in tfidf_neighbours(vec):
        key = edge_key(a, b)
        if key not in sim or sim[key]["score"] < c:
            s, t = sorted((a, b))
            sim[key] = edge(s, t, "similar", "similar", False, c)
    return ref, sim


def from_graph(path: Path):
    g = json.loads(path.read_text(encoding="utf-8"))
    by_id = {n["id"]: n["path"] for n in g["nodes"]}
    ref, sim = {}, {}
    for e in g["edges"]:
        s, t = by_id[e["source"]], by_id[e["target"]]
        quote = (e.get("evidence") or [{}])[0].get("quote", "")
        if e["reason"] in EXPLICIT:
            ref.setdefault(edge_key(s, t), edge(s, t, e["reason"], e["reason"], True, 1.0, quote))
        elif e["reason"] == "similar":
            sim.setdefault(edge_key(s, t), edge(s, t, "similar", "similar", False, round(e["score"], 4)))
    return ref, sim


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--from-graph")
    args = ap.parse_args()
    project = ROOT / "benchmark" / "gt" / args.project / "project"
    texts = read_files(project)
    vec = tfidf(texts)
    paths = list(texts)
    if args.from_graph:
        ref, sim = from_graph(Path(args.from_graph))
        source, made = "system", str(args.from_graph)
    else:
        ref, sim = from_rules(texts, vec)
        source, made = "rule", "make_baselines.py rules (mirror of srcs/candidates.py)"
    out = HERE / "data" / args.project / "graphs"
    out.mkdir(parents=True, exist_ok=True)
    for name, edges, (groups, gid) in (("obsidian", ref, obsidian_graph(paths, ref, texts)),
                                       ("similar", sim, similar_graph(paths, sim, texts, vec))):
        g = graph(paths, edges, groups, gid, texts, name, source, made)
        (out / f"{name}.json").write_text(json.dumps(g, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{name}: {len(g['nodes'])} files, {len(g['edges'])} links, groups: {[x['name'] for x in groups]}")


if __name__ == "__main__":
    main()
