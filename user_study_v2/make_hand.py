"""Stand-in ProjectWiki outputs for the study, made by hand from the ground truth (source: "hand").

Replace each file with the real pipeline output when it exists (keep the file name, set meta.source "system"):
  graphs/ours.json          <- final_graph.json of `projectwiki build <project>`
  intents/<id>.json  graph  <- final_graph.json of `projectwiki build <project> --setup` with the same three answers
                     priority_files <- meta.setup.files of that view
  corrections/<id>.json report <- feedback_changes() report of `projectwiki correct` with the option's events

What is made here:
  ours       gt.json: groups, links (a -> b is source -> target), study_text.py summaries and link sentences.
             Key links (gt required) score 0.9, weak links 0.6.
  intents    talk, handover: groups from groupings.json, links from purposes.json (needed -> 0.95, optional kept,
             the rest faded to 0.3, nothing removed), priority files by the pipeline's own rule
             (srcs/initial_preferences.py priority_nodes, copied below).
             The handover graph carries two planted mistakes for task 2-2 (see PLANT).
  corrections one file per planted mistake, one report per answer the participant can give. Same format as
             projectwiki/srcs/feedback_changes.py. Fact errors (edge_wrong) change only that link, as in
             docs/ARCHITECTURE.md (they are left out of the preference signal for other links).

usage: python user_study_v2/make_hand.py
"""
from __future__ import annotations

import copy
import json
import posixpath
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "user_study"))
from study_text import GDESC, KX, SUM  # noqa: E402

GT = ROOT / "benchmark" / "gt"
MAIN, PRACTICE = "mock_plant_fewshot", "mock_sleep_grades"
VISIBLE = ("proposed", "confirmed")
FEEDBACK_TYPES = {"edge_add": "빠진 연결 추가", "edge_wrong": "잘못된 연결 (사실 오류)",
                  "edge_irrelevant": "관련은 있지만 목적상 불필요", "edge_confirm": "맞는 연결 (승인)",
                  "node_move": "다른 그룹으로 이동", "node_ungroup": "그룹에서 빼기"}
HAND = "make_hand.py from benchmark/gt (stand-in until the pipeline output exists)"

# the three setup questions (projectwiki/srcs/setup_form.html), answered for each intent
INTENTS = {
    "talk": {"label": "이번 주 랩미팅 발표", "grouping": "versions", "purpose_id": "talk",
             "setup": {"purpose": "랩미팅 발표 준비. 결과 표와 그림이 어디서 나왔는지 확인",
                       "priority": "결과 표와 그래프",
                       "grouping": "옛 초안(v1)은 따로, 지금 발표 자료는 한데 묶기"}},
    "handover": {"label": "후배에게 코드 인수인계", "grouping": "component", "purpose_id": "handover",
                 "setup": {"purpose": "후배에게 코드 인수인계. 학습·평가를 다시 돌리는 데 필요한 것만",
                           "priority": "코드와 설정 파일",
                           "grouping": "방법 구성요소(FreqMix, 코사인 헤드, 일관성 손실)별로"}},
}

# planted mistakes in the handover graph: [issue link, links like it that follow the same correction]
PLANT = {
    "issue1": {"edge": ["figures/accuracy_vs_shots.png", "paper/talk_outline.md"], "planted": "up",
               "like": [["paper/leafproto_draft_v2.pdf", "paper/talk_outline.md"],
                        ["notes/meeting_2026-09-17.md", "paper/leafproto_draft_v2.pdf"]],
               "hint": {"meaning": "발표 개요(talk_outline.md)에서 정확도 그래프를 발표에 쓴다는 연결입니다.",
                        "state": "지금 굵게(중요하게) 표시되어 있습니다.",
                        "ask": "후배가 학습과 평가를 다시 돌리는 데 이 연결이 필요할까요? 필요하면 [필요한 연결], 필요 없으면 [지금은 불필요]를 고르세요."},
               "kind": "발표 자료 ↔ 그림·논문",
               "what": ["발표 개요가 논문 초안을 설명하는 연결", "회의록에서 논문 초안을 다룬 연결"],
               "learned": {"edge_irrelevant": "‘인수인계’에서는 발표·논문 자료끼리 잇는 연결을 중요하지 않게 보셨습니다. 후배가 학습과 평가를 다시 돌리는 데 쓰이지 않는 연결이기 때문입니다.",
                           "edge_confirm": "‘인수인계’에서도 발표·논문 자료끼리 잇는 연결이 필요하다고 보셨습니다. 후배가 결과가 어디에 쓰였는지도 알아야 한다는 뜻으로 읽었습니다."},
               "why": {"edge_irrelevant": "학습·평가를 다시 돌리는 데는 쓰이지 않아 흐리게 했습니다.",
                       "edge_confirm": "같은 기준으로 보면 이 연결도 필요해서 조금 굵게 했습니다."}},
    "issue2": {"edge": ["configs/base.yaml", "src/train.py"], "planted": "down",
               "like": [["configs/base.yaml", "configs/fewshot_5way.yaml"],
                        ["configs/fewshot_5way.yaml", "src/train.py"]],
               "hint": {"meaning": "학습 코드(train.py)가 기본 설정 파일(base.yaml)을 읽어서 학습한다는 연결입니다.",
                        "state": "지금 흐리게(덜 중요하게) 표시되어 있습니다.",
                        "ask": "후배가 학습을 다시 돌리는 데 이 연결이 필요할까요? 필요하면 [필요한 연결], 필요 없으면 [지금은 불필요]를 고르세요."},
               "kind": "설정 ↔ 학습 코드",
               "what": ["5-way 설정이 기본 설정을 이어받는 연결", "학습 코드가 5-way 설정을 읽는 연결"],
               "learned": {"edge_confirm": "‘인수인계’에서는 학습 코드와 설정 파일 사이 연결이 중요하다고 보셨습니다. 후배가 학습을 다시 돌리려면 어떤 설정을 읽는지 알아야 하기 때문입니다.",
                           "edge_irrelevant": "‘인수인계’에서는 학습 코드와 설정 파일 사이 연결이 필요 없다고 보셨습니다."},
               "why": {"edge_confirm": "학습을 다시 돌릴 때 함께 봐야 하는 설정이라 다시 굵게 했습니다.",
                       "edge_irrelevant": "같은 기준으로 이 연결도 필요 없다고 보고 숨겼습니다."}},
}

GROUP_DESC = {
    "현재 발표 자료": "지금 발표에 쓰는 최신 논문 초안 v2, 발표 개요, 프로젝트 웹페이지",
    "이전 초안": "예전 버전의 논문 초안 (v1)",
    "FreqMix 증강": "FreqMix 증강 구현, 그 설정, ablation 결과",
    "코사인 프로토타입 헤드": "코사인 프로토타입 head가 있는 모델 코드와 5-way 설정",
    "일관성 손실": "일관성 손실을 쓰는 학습 코드",
}


def key(a: str, b: str) -> str:
    return f"{a}|{b}" if a < b else f"{b}|{a}"


def load(proj: str, name: str) -> dict:
    return json.loads((GT / proj / name).read_text(encoding="utf-8"))


def ftype(path: str) -> str:
    return {".py": "python", ".md": "markdown", ".pdf": "pdf", ".ipynb": "notebook", ".png": "image"}.get(
        posixpath.splitext(path)[1].lower(), "text")


# ---- copied from projectwiki/srcs/initial_preferences.py (main @ f45437f) ----
MATERIAL_HINTS = {"results": r"결과|그림|그래프|시각화|result|figure|plot", "code": r"코드|설정|소스|구현|code|source|config",
                  "docs": r"문서|논문|보고서|document|paper|report", "notes": r"회의|메모|노트|meeting|memo|notes?"}


def material_kind(path: str, file_type: str) -> str | None:
    path = path.lower()
    parts = set(re.split(r"[\W_]+", path))
    ext = posixpath.splitext(path)[1]
    if parts & {"notes", "note", "meeting", "meetings", "memo"}:
        return "notes"
    if file_type == "image" or parts & {"result", "results", "figures", "plots", "metrics", "outputs"}:
        return "results"
    if file_type in {"python", "notebook"} or ext in {".yaml", ".yml", ".toml", ".ini", ".cfg", ".sh", ".js", ".ts",
                                                       ".tsx", ".jsx", ".c", ".cpp", ".java", ".go", ".rs"} \
            or parts & {"src", "config", "configs"}:
        return "code"
    if file_type in {"markdown", "pdf"} or ext in {".rst", ".tex", ".docx"}:
        return "docs"
    return None


def priority_nodes(nodes: list[dict], request: str) -> list[str]:
    if not request:
        return []
    request = request.casefold().replace("\\", "/")
    kinds = {kind for kind, pattern in MATERIAL_HINTS.items() if re.search(pattern, request)}
    named, similar = [], []
    for node in nodes:
        path = node["path"].casefold()
        if posixpath.splitext(path)[1] and (path in request or posixpath.basename(path) in request):
            named.append(node["id"])
        elif material_kind(node["path"], node["type"]) in kinds:
            similar.append(node["id"])
    return named + similar
# ---------------------------------------------------------------------------


def ours(proj: str) -> dict:
    gt = load(proj, "gt.json")
    groups, nodes = [], {}
    for gi, g in enumerate(gt["groups"]):
        gid = f"g{gi + 1}"
        groups.append({"id": gid, "name": g["name"], "members": list(g["members"]), "origin": "ai",
                       "description": GDESC[proj][gi]})
        for m in g["members"]:
            nodes[m] = {"id": m, "path": m, "type": ftype(m), "title": posixpath.basename(m), "group": gid,
                        "role": "", "summary": SUM[proj][m]}
    edges = []
    for k, e in enumerate(gt["edges"]):
        src, tgt = (e["b"], e["a"]) if e.get("direction") == "b_to_a" else (e["a"], e["b"])
        ev = e.get("evidence") or {}
        explicit = e["layer"] == "explicit"
        reason = ("imports" if "import" in e.get("note", "")[:12] else "mentions") if explicit else "similar"
        edges.append({"id": key(src, tgt), "source": src, "target": tgt, "relation": e["relation"], "reason": reason,
                      "direct": explicit, "score": 0.9 if e.get("required") else 0.6, "label": KX[proj][k],
                      "evidence": [{"chunk_id": "", "file_id": ev["file"], "locator": "", "quote": ev["span"][:360]}]
                      if ev.get("span") else [],
                      "origin": "ai", "status": "proposed", "correction": ""})
    return {"meta": {"source": "hand", "method": "ours", "made_from": HAND},
            "nodes": list(nodes.values()), "groups": groups, "edges": edges}


def intent(base: dict, iid: str) -> dict:
    spec = INTENTS[iid]
    g = copy.deepcopy(base)
    pref = next(p for p in load(MAIN, "groupings.json")["preferences"] if p["id"] == spec["grouping"])
    g["groups"] = [{"id": f"i{gi + 1}", "name": x["name"], "members": list(x["members"]), "origin": "ai",
                    "description": GROUP_DESC.get(x["name"], next((y["description"] for y in base["groups"]
                                                                    if y["name"] == x["name"]), ""))}
                   for gi, x in enumerate(pref["groups"])]
    gid = {m: x["id"] for x in g["groups"] for m in x["members"]}
    for n in g["nodes"]:
        n["group"] = gid[n["path"]]
    pur = next(p for p in load(MAIN, "purposes.json")["purposes"] if p["id"] == spec["purpose_id"])
    need = {key(*x) for x in pur["needed"]}
    opt = {key(*x) for x in pur["optional"]}
    notes = {key(*k.split("|")): re.sub(r"\s*\([^)]*\)\s*$", "", v) for k, v in pur.get("notes", {}).items()}
    why = {}
    for e in g["edges"]:
        if e["id"] in need:
            e["score"] = 0.95
            if e["id"] in notes:
                why[e["id"]] = notes[e["id"]]
        elif e["id"] not in opt:
            e["score"] = 0.3
    if iid == "handover":
        for p in PLANT.values():
            for pair in [p["edge"], *p["like"]]:
                e = next(x for x in g["edges"] if x["id"] == key(*pair))
                e["score"] = 0.95 if p["planted"] == "up" else 0.3
                why.pop(e["id"], None)
    g["meta"] = {"source": "hand", "method": "ours", "made_from": HAND}
    return {"meta": {"source": "hand", "made_from": HAND}, "id": iid, "label": spec["label"], "setup": spec["setup"],
            "priority_files": priority_nodes(g["nodes"], spec["setup"]["priority"]), "why": why, "graph": g}


def state(e: dict) -> dict:
    return {"visible": e["status"] in VISIBLE, "status": e["status"], "relation": e["relation"], "score": round(e["score"], 4)}


def corrections(handover: dict) -> dict:
    E = {e["id"]: e for e in handover["graph"]["edges"]}
    out = {}
    for iid, p in PLANT.items():
        target = E[key(*p["edge"])]
        like = [E[key(*x)] for x in p["like"]]

        def report(action, after, auto, note="", learned=""):
            direct = {"files": [after.get("source", target["source"]), after.get("target", target["target"])],
                      "before": state(target), "after": state({**target, **after}), "reason": after.get("correction", ""),
                      "action": action}
            return {"direct": [direct], "automatic": auto, "corrector": "best-of-n", "applied": 1, "note": note,
                    "learned": learned}

        # each like-link gets its own reason: what the link is, then how the learned preference applies to it
        say = lambda t: [f"{w}입니다. {p['why'][t]}" for w in p["what"]]  # noqa: E731

        def moved(e, score=None, status=None, why=""):
            new = {**e, **({"score": score} if score is not None else {}), **({"status": status} if status else {})}
            return {"files": [e["source"], e["target"]], "before": state(e), "after": state(new), "reason": why}

        events = lambda t, **kw: [{"type": t, "source": target["source"], "target": target["target"], **kw}]  # noqa: E731
        o = {}
        if p["planted"] == "up":   # raised by mistake: "목적상 불필요" is the expected answer
            o["edge_irrelevant"] = {"events": events("edge_irrelevant"), "report": report(
                FEEDBACK_TYPES["edge_irrelevant"], {"status": "removed_irrelevant"},
                [moved(e, 0.3, None, w) for e, w in zip(like, say("edge_irrelevant"))], learned=p["learned"]["edge_irrelevant"])}
            o["edge_confirm"] = {"events": events("edge_confirm", relation=target["relation"]), "report": report(
                FEEDBACK_TYPES["edge_confirm"], {"status": "confirmed", "score": 1.0},
                [moved(e, 0.98, None, w) for e, w in zip(like, say("edge_confirm"))], learned=p["learned"]["edge_confirm"])}
        else:                      # faded by mistake: "맞는 연결" is the expected answer
            o["edge_confirm"] = {"events": events("edge_confirm", relation=target["relation"]), "report": report(
                FEEDBACK_TYPES["edge_confirm"], {"status": "confirmed", "score": 1.0},
                [moved(e, 0.9, None, w) for e, w in zip(like, say("edge_confirm"))], learned=p["learned"]["edge_confirm"])}
            o["edge_irrelevant"] = {"events": events("edge_irrelevant"), "report": report(
                FEEDBACK_TYPES["edge_irrelevant"], {"status": "removed_irrelevant"},
                [moved(e, None, "removed_by_corrector", w) for e, w in zip(like, say("edge_irrelevant"))],
                learned=p["learned"]["edge_irrelevant"])}
        o["edge_wrong"] = {"events": events("edge_wrong"), "report": report(
            FEEDBACK_TYPES["edge_wrong"], {"status": "removed_wrong"}, [],
            "‘틀린 연결’은 그 연결 하나만 고칩니다. 사실이 틀린 경우라서 다른 연결에는 영향을 주지 않습니다.")}
        out[iid] = {"meta": {"source": "hand", "made_from": HAND}, "intent": "handover",
                    "edge": [target["source"], target["target"]], "planted": p["planted"], "hint": p["hint"],
                    "kind": p["kind"], "options": o}
    return out


def write(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    print(path.relative_to(HERE))


def main():
    for proj in (MAIN, PRACTICE):
        write(HERE / "data" / proj / "graphs" / "ours.json", ours(proj))
    base = ours(MAIN)
    its = {i: intent(base, i) for i in INTENTS}
    for i, x in its.items():
        write(HERE / "data" / MAIN / "intents" / f"{i}.json", x)
    for c, x in corrections(its["handover"]).items():
        write(HERE / "data" / MAIN / "corrections" / f"{c}.json", x)


if __name__ == "__main__":
    main()
