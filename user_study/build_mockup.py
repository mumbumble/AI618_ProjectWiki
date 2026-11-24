"""Build the clickable user-study mockup (user_study/study_mockup.html).

Reads the two mock folders and their ground truth from benchmark/gt/, the Korean text from
study_text.py, and fills mockup_template.html. Everything ends up in one HTML file.

usage: python user_study/build_mockup.py [out.html]
"""
import base64
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from study_text import GDESC, KX, SUM  # noqa: E402

PRACTICE, MAIN = "mock_sleep_grades", "mock_plant_fewshot"
REL = {"implements": "구현함", "uses": "사용함", "produces": "만들어 냄", "describes": "설명함", "extends": "확장함",
       "same_method": "같은 방법", "supports": "뒷받침함", "contradicts": "모순", "compares": "비교함",
       "same_topic": "같은 주제", "duplicate": "같은 문서의 다른 판", "other": "언급함"}
UNDIRECTED = ("same_method", "same_topic", "compares", "duplicate", "other")

# study steps. "pid" picks a purpose from benchmark/gt/<proj>/purposes.json; file answers are paths.
STEPS = {
    "practice": {"proj": PRACTICE, "purpose": "과제 보고서 마무리 중. 보고서에 쓴 수치가 어디서 나왔는지 확인하고 싶음",
                 "qs": [{"t": "mc", "q": "데이터 정제 후 분석에 쓰인 행 수는?", "o": ["32행", "28행", "31행", "29행"], "a": 1},
                        {"t": "file", "q": "수면 시간–성적 산점도를 만든 파일은 무엇인가요?", "a": "notebooks/01_eda.ipynb"}]},
    "t1a": {"proj": MAIN, "pid": "talk", "view": "folder",
            "qs": [{"t": "mc", "q": "결과 슬라이드에 넣을 LeafProto 5-shot 정확도는?", "o": ["86.1%", "87.4%", "83.6%", "90.6%"], "a": 1},
                   {"t": "mc", "q": "9월 회의에서 Figure 2 캡션을 고치기로 한 이유는?",
                    "o": ["1-shot의 격차가 5-shot보다 커서", "수치에 오타가 있어서", "v1 그림을 써서", "축 이름이 틀려서"], "a": 0}]},
    "t1b": {"proj": MAIN, "pid": "talk", "view": "tool",
            "qs": [{"t": "mc", "q": "ablation에서 성능이 가장 크게 떨어진 구성은?",
                    "o": ["FreqMix 제거", "cosine head 제거", "consistency loss 제거", "전체 주파수 혼합"], "a": 0},
                   {"t": "file", "q": "발표 Figure 2(정확도 그래프)를 만드는 코드 파일은 무엇인가요?", "a": "src/plot_results.py"}]},
    "t2": {"proj": MAIN, "pid": "handover", "review": 6, "seed_hides": 2},
}


def content(path: Path) -> dict:
    ext = path.suffix.lower()
    if ext == ".png":
        return {"kind": "image", "data": "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()}
    if ext == ".pdf":
        return {"kind": "pdf", "data": base64.b64encode(path.read_bytes()).decode()}
    if ext == ".ipynb":
        nb = json.loads(path.read_text(encoding="utf-8"))
        return {"kind": "nb", "data": [[c["cell_type"], "".join(c.get("source", []))] for c in nb["cells"]]}
    return {"kind": "text", "ext": ext.lstrip("."), "data": path.read_text(encoding="utf-8", errors="replace")}


def direction(e) -> int:
    """1: a -> b, -1: b -> a, 0: no direction."""
    if e["relation"] in UNDIRECTED or e.get("direction", "") in ("both", "unknown", ""):
        return 0
    return -1 if e["direction"] == "b_to_a" else 1


def sentence(e) -> str:
    a, b = e["a"].split("/")[-1], e["b"].split("/")[-1]
    arrow = {0: f"{a} ↔ {b}", 1: f"{a} → {b}", -1: f"{b} → {a}"}[direction(e)]
    return f"{arrow}: {REL.get(e['relation'], e['relation'])}"


def suggestions(gt_edges, gof) -> list:
    """System suggestions for task 2: for each link, the links most similar to it.
    score = 2*(same pair of groups) + (shares a file) + (same relation); keeps candidates scoring 2 or more.
    It does not look at the answer key."""
    table = []
    for i, ei in enumerate(gt_edges):
        gi = {gof[ei["a"]], gof[ei["b"]]}
        cand = []
        for j, ej in enumerate(gt_edges):
            if j == i:
                continue
            score = (2 * (gi == {gof[ej["a"]], gof[ej["b"]]})
                     + bool({ei["a"], ei["b"]} & {ej["a"], ej["b"]})
                     + (ei["relation"] == ej["relation"]))
            if score >= 2:
                cand.append((-score, j))
        table.append([[j, -s] for s, j in sorted(cand)[:8]])
    return table


def folder(proj: str, purposes: dict) -> dict:
    root = ROOT / "benchmark" / "gt" / proj
    gt = json.loads((root / "gt.json").read_text(encoding="utf-8"))
    files = [m for g in gt["groups"] for m in g["members"]]
    idx = {f: i for i, f in enumerate(files)}
    gof = {f: gi for gi, g in enumerate(gt["groups"]) for f in g["members"]}
    edges = []
    for k, e in enumerate(gt["edges"]):
        ev = e.get("evidence") or {}
        edges.append({"a": idx[e["a"]], "b": idx[e["b"]], "s": sentence(e), "rel": REL.get(e["relation"], e["relation"]),
                      "direct": e["layer"] == "explicit", "d": direction(e), "ev": ev.get("span", ""), "evf": ev.get("file", ""),
                      "x": KX[proj][k]})
    # answer key per purpose (2 needed / 1 optional / 0 not needed); used only for the result table
    st = {}
    pfile = root / "purposes.json"
    for p in (json.loads(pfile.read_text(encoding="utf-8"))["purposes"] if pfile.exists() else []):
        key = lambda a, b: "|".join(sorted((a, b)))  # noqa: E731
        need, opt = {key(*x) for x in p["needed"]}, {key(*x) for x in p["optional"]}
        st[p["id"]] = [2 if key(e["a"], e["b"]) in need else 1 if key(e["a"], e["b"]) in opt else 0 for e in gt["edges"]]
        purposes[p["id"]] = p["text"]
    return {"files": files, "groups": [[g["name"], [idx[m] for m in g["members"]]] for g in gt["groups"]],
            "sum": [SUM[proj][f] for f in files], "gdesc": GDESC[proj],
            "content": [content(root / "project" / f) for f in files],
            "edges": edges, "st": st, "drift": suggestions(gt["edges"], gof)}


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "study_mockup.html"
    purposes = {}
    folders = {p: folder(p, purposes) for p in (PRACTICE, MAIN)}
    steps = json.loads(json.dumps(STEPS))
    for s in steps.values():
        if "pid" in s:
            s["purpose"] = purposes[s["pid"]]
        for q in s.get("qs", []):
            if q["t"] == "file":
                q["a"] = folders[s["proj"]]["files"].index(q["a"])
    data = ("const FD=" + json.dumps(folders, ensure_ascii=False) + ";const ST=" + json.dumps(steps, ensure_ascii=False) + ";")
    html = (HERE / "mockup_template.html").read_text(encoding="utf-8").replace("/*DATA*/", data.replace("</", "<\\/"))
    out.write_text(html, encoding="utf-8")
    print(out, f"{out.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
