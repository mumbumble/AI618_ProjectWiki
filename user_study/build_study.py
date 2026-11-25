"""Build the user-study page (user_study/projectwiki_study.html).

Reads the two mock folders and their ground truth from benchmark/gt/, the Korean text from
study_text.py, and fills study_template.html. Everything ends up in one HTML file.

usage: python user_study/build_study.py [out.html]
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

# name shown to participants instead of the benchmark folder name
NAME = {PRACTICE: "stat_hw_sleep", MAIN: "leafproto_project"}

# folder introduction shown before the first task in each folder (no timer).
# "dirs": top-level folder -> what is in it; the page adds the file count.
INTRO = {
    MAIN: {"who": "식물 잎 사진 몇 장만 보고 병을 분류하는 모델(LeafProto)을 연구하는 대학원생의 폴더입니다. "
                  "지금은 논문 초안을 다듬는 중이고, 다음 주 랩미팅에서 결과를 발표합니다.",
           "dirs": [["src", "모델, 학습, 평가, 그래프 그리는 코드"], ["configs", "학습 설정"], ["logs", "학습 기록"],
                    ["results", "실험 결과 표"], ["figures", "논문과 발표에 쓰는 그림"], ["paper", "논문 초안 두 판, 발표 개요"],
                    ["docs", "방법 설명, 관련 연구 정리"], ["papers", "다른 논문을 읽고 쓴 노트"], ["notes", "랩미팅 회의록, 아이디어 메모"],
                    ["site", "프로젝트 소개 웹페이지"], ["README.md", "프로젝트 소개와 실행 방법"],
                    ["admin, reading", "연구와 상관없는 파일"]],
           "flow": ["코드 (src)", "실험 결과 (results)", "그림 (figures)", "논문·발표 (paper)"]},
    PRACTICE: {"who": "통계 수업 팀 과제 폴더입니다. 대학생의 수면 시간, 아르바이트 시간과 성적의 관계를 분석해 보고서를 냈습니다.",
               "dirs": [["data", "설문 원자료, 정제한 데이터, 변수 설명"], ["src", "데이터 정제 코드"], ["notebooks", "분석 노트북"],
                        ["report", "최종 보고서와 그림"], ["assignment", "과제 명세"], ["references", "선행 연구 노트"],
                        ["notes", "팀 회의록, TA 피드백"], ["README.md", "과제 소개"], ["misc", "과제와 상관없는 파일"]],
               "flow": ["데이터 (data)", "정제 코드 (src)", "분석 노트북 (notebooks)", "보고서 (report)"]},
}

# study steps. "pid" picks the answer key from benchmark/gt/<proj>/purposes.json; "purpose" is the line shown
# (rewritten from purposes.json in plain sentences). File answers are paths.
STEPS = {
    "practice": {"proj": PRACTICE, "purpose": "과제 보고서를 마무리하는 중입니다. 보고서에 쓴 수치가 어디서 나왔는지 확인하려고 합니다.",
                 "qs": [{"t": "mc", "q": "데이터를 정제한 뒤 분석에 쓰인 행은 몇 개인가요?", "o": ["32행", "28행", "31행", "29행"], "a": 1,
                         "hint": "‘데이터 및 코드북’ 그룹의 clean_student_sleep_survey_2026.csv를 열면 요약과 내용에서 28행을 확인할 수 있습니다. "
                                 "32행은 정제하기 전 원자료입니다."},
                        {"t": "file", "q": "수면 시간–성적 산점도를 만든 파일은 무엇인가요?", "a": "notebooks/01_eda.ipynb",
                         "hint": "산점도 그림(sleep_vs_grade_scatter.png)을 열고 오른쪽 연결 목록을 보면 ‘01_eda.ipynb · 만들어 냄’이 있습니다. "
                                 "그림에서 출발해 연결을 따라가면 만든 파일을 찾을 수 있습니다."}]},
    "t1a": {"proj": MAIN, "pid": "talk", "view": "folder",
            "purpose": "다음 주 랩미팅에서 발표합니다. 방법 슬라이드는 다 만들었고, 결과 슬라이드에 넣을 표와 그림이 어디서 나왔는지 확인하려고 합니다.",
            "qs": [{"t": "mc", "q": "결과 슬라이드에 넣을 LeafProto 5-shot 정확도는?", "o": ["86.1%", "87.4%", "83.6%", "90.6%"], "a": 1},
                   {"t": "mc", "q": "9월 회의에서 Figure 2 캡션을 고치기로 한 이유는?",
                    "o": ["1-shot의 격차가 5-shot보다 커서", "수치에 오타가 있어서", "v1 그림을 써서", "축 이름이 틀려서"], "a": 0}]},
    "t1b": {"proj": MAIN, "pid": "talk", "view": "tool",
            "purpose": "다음 주 랩미팅에서 발표합니다. 방법 슬라이드는 다 만들었고, 결과 슬라이드에 넣을 표와 그림이 어디서 나왔는지 확인하려고 합니다.",
            "qs": [{"t": "mc", "q": "결과 표(main_results.csv)의 숫자를 만들어 낸 코드 파일은?",
                    "o": ["train.py", "evaluate.py", "plot_results.py", "utils.py"], "a": 1},
                   {"t": "file", "q": "발표 Figure 2(정확도 그래프)를 만드는 코드 파일은 무엇인가요?", "a": "src/plot_results.py"}]},
    "t2": {"proj": MAIN, "pid": "handover", "review": 6, "seed_hides": 2,
           "purpose": "후배에게 실험 코드를 넘겨주려고 합니다. 학습과 평가를 다시 돌리는 데 필요한 것만 남기려고 합니다."},
    # practice step 5: the link to hide (not needed for checking the report numbers)
    "practice_hide": ["notes/team_meeting.md", "assignment/project_spec.pdf"],
}

# Google Forms. "result" gets one column per value (key -> entry id, read from the form editor);
# "folder" is opened with name/email/step prefilled. Empty url: the page sends nothing.
FORMS = {
    "result": {  # ProjectWiki 스터디 결과 수신 (자동). Not shown to participants
        "url": "https://docs.google.com/forms/d/e/1FAIpQLSe5fK4-gecn-FMDMn876-r7Bnu7IFRF_uo8HnAI9v-3kYF0kA/formResponse",
        "fields": {
            "name": "entry.561842790", "email": "entry.546957036", "level": "entry.1985213836",
            "organize": "entry.285785535", "nfiles": "entry.1179243453", "total_min": "entry.1669815023",
            "t1a_ok": "entry.802791420", "t1a_sec": "entry.1101301982", "t1a_opens": "entry.1957609189",
            "t1b_ok": "entry.1878290250", "t1b_sec": "entry.952112514", "t1b_opens": "entry.1943371007",
            "practice_sec": "entry.388341295", "c1": "entry.892676460", "c1_why": "entry.2024573725",
            "t2_sys": "entry.698169169", "t2_rnd": "entry.1578862182", "c2": "entry.51950815", "c2_why": "entry.256525312",
            "reuse": "entry.1130392397", "trust": "entry.84602597", "good": "entry.1451534783", "bad": "entry.252477700",
            "data": "entry.1775516221",
        },
    },
    "folder": {  # ProjectWiki 스터디 · 본인 폴더
        "url": "https://docs.google.com/forms/d/e/1FAIpQLSch1PXOGqvCAvF1m6kweQ3Cglu4o21peG3flnxDeQEmGnrgjA/viewform",
        "stage": "처음: 폴더 보내기",
        "fields": {"name": "entry.1981534530", "email": "entry.395872472", "stage": "entry.1792304602"},
    },
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
    return {"name": NAME[proj], "intro": INTRO[proj], "files": files, "groups": [[g["name"], [idx[m] for m in g["members"]]] for g in gt["groups"]],
            "sum": [SUM[proj][f] for f in files], "gdesc": GDESC[proj],
            "content": [content(root / "project" / f) for f in files],
            "edges": edges, "st": st, "drift": suggestions(gt["edges"], gof)}


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "projectwiki_study.html"
    purposes = {}
    folders = {p: folder(p, purposes) for p in (PRACTICE, MAIN)}
    steps = json.loads(json.dumps(STEPS))
    ph = steps.pop("practice_hide")
    pf = folders[PRACTICE]["files"]
    steps["practice"]["hide"] = next(j for j, e in enumerate(folders[PRACTICE]["edges"])
                                     if {e["a"], e["b"]} == {pf.index(ph[0]), pf.index(ph[1])})
    for s in steps.values():
        if "pid" in s and "purpose" not in s:
            s["purpose"] = purposes[s["pid"]]
        for q in s.get("qs", []):
            if q["t"] == "file":
                q["a"] = folders[s["proj"]]["files"].index(q["a"])
    data = ("const FD=" + json.dumps(folders, ensure_ascii=False) + ";const ST=" + json.dumps(steps, ensure_ascii=False)
            + ";const FORMS=" + json.dumps(FORMS, ensure_ascii=False) + ";")
    html = (HERE / "study_template.html").read_text(encoding="utf-8").replace("/*DATA*/", data.replace("</", "<\\/"))
    out.write_text(html, encoding="utf-8")
    print(out, f"{out.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
