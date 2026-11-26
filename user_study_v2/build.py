"""Build the v2 study page: check the data files, then put them into study_template.html (one HTML file).

  python user_study_v2/make_baselines.py mock_plant_fewshot   # task 1 comparisons (rule)
  python user_study_v2/make_baselines.py mock_sleep_grades
  python user_study_v2/make_hand.py                           # stand-ins for ProjectWiki outputs (hand)
  python user_study_v2/build.py [out.html]                    # -> user_study_v2/study.html

Results are sent to an Apps Script web app when user_study_v2/send.json has {"url": ".../exec"}
(user_study/apps_script/Code.gs stores {kind:"result"} posts). Without it the end page offers a file download.

Every data file says where it came from in meta.source: "system" (pipeline output), "rule" (made by a
fixed rule), or "hand" (stand-in). The build lists them and warns while any "hand" file is left; the page
then shows a small "시험판" mark.
"""
from __future__ import annotations

import ast
import base64
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DATA = HERE / "data"
MAIN, PRACTICE = "mock_plant_fewshot", "mock_sleep_grades"
VISIBLE = ("proposed", "confirmed")

NAME = {MAIN: "leafproto_project", PRACTICE: "stat_hw_sleep"}
INTRO = {
    MAIN: {"who": "식물 잎 사진 몇 장만 보고 병을 분류하는 모델(LeafProto)을 연구하는 대학원생의 폴더입니다. "
                  "지금은 논문 초안을 다듬는 중이고, 다음 주 랩미팅에서 결과를 발표합니다.",
           "dirs": [["src", "모델, 학습, 평가, 그래프 그리는 코드"], ["configs", "학습 설정"], ["logs", "학습 기록"],
                    ["results", "실험 결과 표"], ["figures", "논문과 발표에 쓰는 그림"], ["paper", "논문 초안 두 판, 발표 개요"],
                    ["docs", "방법 설명, 관련 연구 정리"], ["papers", "다른 논문을 읽고 쓴 노트"], ["notes", "랩미팅 회의록, 아이디어 메모"],
                    ["site", "프로젝트 소개 웹페이지"], ["README.md", "프로젝트 소개와 실행 방법"], ["admin, reading", "연구와 상관없는 파일"]],
           "short": "잎 사진 몇 장으로 식물 병을 가려내는 모델을 연구하는 대학원생의 폴더입니다. 지금은 논문을 다듬으면서 랩미팅 발표를 준비하고 있습니다.",
           "flow": ["학습·평가 코드", "결과 표", "그림", "논문·발표"]},
    PRACTICE: {"who": "통계 수업 팀 과제 폴더입니다. 대학생의 수면 시간, 아르바이트 시간과 성적의 관계를 분석해 보고서를 냈습니다.",
               "dirs": []},
}
# conditions of task 1: file name in data/<MAIN>/graphs, and what is told after the comparison
METHODS = {
    "obsidian": "Obsidian식: 파일 안에 적힌 참조(import, 링크, 파일 이름 언급)만 선으로 잇는 방식입니다. Obsidian의 그래프 뷰가 이렇게 그립니다.",
    "similar": "내용 유사도: 내용이 비슷한 파일끼리 잇는 방식입니다. 많은 문서 정리 도구가 ‘관련 문서’를 이렇게 찾습니다.",
    "ours": "ProjectWiki: 파일 사이의 관계를 판단해 근거를 붙이고, 비슷한 파일끼리 그룹으로 묶습니다. 이번 연구에서 만든 도구입니다.",
}
STUDY = {"who": "KAIST AI618 수업 팀 프로젝트", "delete_by": "2026년 12월 31일"}


def dict_literal(path: Path, name: str) -> dict:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        targets = [t.id for t in getattr(node, "targets", []) if isinstance(t, ast.Name)]
        if name in targets:
            return ast.literal_eval(node.value)
    raise KeyError(name)


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


def read(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


class Check:
    def __init__(self):
        self.errors, self.sources = [], []

    def need(self, ok: bool, msg: str):
        if not ok:
            self.errors.append(msg)

    def graph(self, name: str, g: dict, files: list[str]):
        self.sources.append((name, g.get("meta", {}).get("source", "?")))
        paths = [n["path"] for n in g["nodes"]]
        self.need(sorted(paths) == sorted(files), f"{name}: files differ from the project folder")
        ids = {n["id"] for n in g["nodes"]}
        gids = {x["id"] for x in g["groups"]}
        for n in g["nodes"]:
            self.need(n["group"] is None or n["group"] in gids, f"{name}: {n['path']} in unknown group {n['group']}")
        for e in g["edges"]:
            self.need(e["source"] in ids and e["target"] in ids, f"{name}: link {e['id']} has an unknown file")
            for k in ("relation", "reason", "direct", "score", "status"):
                self.need(k in e, f"{name}: link {e['id']} has no {k}")


def project(proj: str, ck: Check) -> dict:
    root = ROOT / "benchmark" / "gt" / proj / "project"
    files = sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())
    graphs = {}
    for f in sorted((DATA / proj / "graphs").glob("*.json")):
        g = read(f)
        ck.graph(f"{proj}/graphs/{f.name}", g, files)
        graphs[f.stem] = g
    return {"name": NAME[proj], "intro": INTRO[proj], "files": files,
            "content": {f: content(root / f) for f in files}, "graphs": graphs}


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "study.html"
    ck = Check()
    projects = {p: project(p, ck) for p in (MAIN, PRACTICE)}
    ck.need(set(METHODS) <= set(projects[MAIN]["graphs"]), f"{MAIN}: missing graphs {set(METHODS) - set(projects[MAIN]['graphs'])}")
    ck.need("ours" in projects[PRACTICE]["graphs"], f"{PRACTICE}: missing graphs/ours.json")
    files = projects[MAIN]["files"]
    intents = {}
    for f in sorted((DATA / MAIN / "intents").glob("*.json")):
        x = read(f)
        ck.graph(f"{MAIN}/intents/{f.name}", x["graph"], files)
        ck.need(all(p in files for p in x["priority_files"]), f"intent {f.stem}: unknown priority file")
        intents[x["id"]] = x
    ck.need(len(intents) == 2, "task 2 needs two intents")
    corrections = {}
    for f in sorted((DATA / MAIN / "corrections").glob("*.json")):
        x = read(f)
        ck.sources.append((f"{MAIN}/corrections/{f.name}", x["meta"]["source"]))
        g = intents.get(x["intent"], {}).get("graph", {"edges": []})
        keys = {"|".join(sorted((e["source"], e["target"]))) for e in g["edges"]}
        ck.need("|".join(sorted(x["edge"])) in keys, f"correction {f.stem}: its link is not in the {x['intent']} graph")
        for t, o in x["options"].items():
            for row in o["report"]["direct"] + o["report"]["automatic"]:
                ck.need("|".join(sorted(row["files"])) in keys, f"correction {f.stem}/{t}: report row not in the graph")
        corrections[f.stem] = x
    ck.need(len(corrections) == 2, "task 2-2 needs two corrections")

    if ck.errors:
        print("data check failed:\n  " + "\n  ".join(ck.errors))
        sys.exit(1)
    hand = [n for n, s in ck.sources if s == "hand"]
    print("data sources:")
    for n, s in ck.sources:
        print(f"  {s:6} {n}")
    if hand:
        print(f"WARNING: {len(hand)} stand-in (hand) data files are included. Replace them with pipeline output "
              f"before the real study.")

    send = read(HERE / "send.json") if (HERE / "send.json").exists() else {}
    D = {"projects": projects, "main": MAIN, "practice": PRACTICE, "methods": METHODS, "intents": intents,
         "corrections": corrections, "hand": hand,
         "relations": dict_literal(ROOT / "projectwiki" / "models" / "visualization.py", "RELATION_NAMES"),
         "feedback_types": dict_literal(ROOT / "projectwiki" / "schema.py", "FEEDBACK_TYPES"),
         "visible": list(VISIBLE)}
    data = ("const D=" + json.dumps(D, ensure_ascii=False) + ";const STUDY=" + json.dumps(STUDY, ensure_ascii=False)
            + ";const SEND=" + json.dumps({"url": send.get("url", "")}) + ";")
    html = (HERE / "study_template.html").read_text(encoding="utf-8")
    html = html.replace("/*CSS*/", (HERE / "base.css").read_text(encoding="utf-8"), 1)
    html = html.replace("/*DATA*/", data.replace("</", "<\\/"), 1)
    out.write_text(html, encoding="utf-8")
    print(out, f"{out.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
