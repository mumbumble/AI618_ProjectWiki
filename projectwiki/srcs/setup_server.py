"""Collect initial preferences and serve the graph with live feedback on loopback."""
from __future__ import annotations

import json
import logging
import re
import secrets
import subprocess
import webbrowser
from dataclasses import replace
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from .. import pipeline
from ..config import Config
from ..schema import Preferences
from .feedback_changes import feedback_changes
from .initial_preferences import pair_feedback, similar_file_pairs
from .levels import final_graph_from_dict
from .record import Record
from .setup_questions import codex_questions, pair_evidence
from .feedback import FeedbackInputError, validate_events
from .wiki_approval import APPROVED_DIR, StaleGraphError, approve_wiki


FORM = Path(__file__).with_name("setup_form.html")
MAX_ANSWER = 1000
# Browser form encoding can take three ASCII characters per byte of UTF-8.
MAX_BODY = MAX_ANSWER * 12 + 256
MAX_FEEDBACK_BODY = 256_000
log = logging.getLogger(__name__)


def pair_questions(cards: list[list[dict]], questions: list[str], summaries: dict[str, str]) -> str:
    if not cards:
        return '<p class="question">추천할 파일 쌍이 없습니다. 첫 그래프 만들기를 눌러 주세요.</p>'
    choices = [("edge_confirm", "함께 보고 싶어요"), ("edge_irrelevant", "이번 목적에는 필요 없어요"), ("skip", "판단하기 어려워요")]
    html = []
    for i, (files, question) in enumerate(zip(cards, questions, strict=True)):
        nodes = []
        for file in files:
            path = Path(file["path"])
            summary = summaries.get(file["path"]) or file["summary"] or "이 파일의 요약을 가져오지 못했어요."
            nodes.append(f'<div class="file-node"><small>{escape(path.parent.as_posix())}/</small>'
                         f'<strong>{escape(path.name)}</strong><p>{escape(summary)}</p></div>')
        options = "".join(
            f'<label><input type="radio" name="pair{i}" value="{value}"'
            f'{" checked" if value == "skip" else ""}> {label}</label>' for value, label in choices)
        a, b = (escape(file["path"]) for file in files)
        direction = (f'<label class="direction">어느 파일에서 다른 파일로 이어질까요?'
                     f'<select name="direction{i}"><option value="">방향은 시스템에 맡기기</option>'
                     f'<option value="forward">{a} → {b}</option>'
                     f'<option value="reverse">{b} → {a}</option></select></label>')
        html.append(f'<details class="pair" name="suggestions"><summary id="pair-title-{i}">{escape(question)}</summary>'
                    f'<div class="pair-content"><div class="sources">'
                     f'{nodes[0]}<span class="pair-link" aria-hidden="true"></span>{nodes[1]}</div>'
                     f'<div class="choices" role="radiogroup" aria-labelledby="pair-title-{i}">{options}</div>{direction}</div></details>')
    return "".join(html)


def run_setup(root: Path, out: Path, cfg: Config, prefs: Preferences, use_codex: bool = False) -> None:
    route = "/" + secrets.token_urlsafe(24)
    result: Path | None = None
    failure: Exception | SystemExit | None = None
    last_feedback: dict | None = None
    approved_view = out / APPROVED_DIR / "view.html"
    prepared = None
    if not approved_view.is_file():
        print("연결 후보를 찾기 위해 프로젝트 파일을 읽는 중입니다.", flush=True)
        prepared = pipeline.prepare_project(root, out, cfg)
        pairs = similar_file_pairs(prepared.record)
        fields = ("purpose", *(f"pair{i}" for i in range(len(pairs))))
        allowed_fields = {*fields, *(f"direction{i}" for i in range(len(pairs)))}
        cards = pair_evidence(prepared.record, pairs)
        template = FORM.read_text(encoding="utf-8")
        values = {"PURPOSE": escape(prefs.purpose),
                  "ROUTE": route, "STAGE": "purpose", "PAIRS": "", "NOTICE": "", "DISPLAYPURPOSE": "", "PROJECT": escape(root.name),
                  "COUNT": str(len(prepared.record.files)),
                  "FILES": "".join(f"<li>{escape(f.path)}</li>" for f in sorted(prepared.record.files, key=lambda f: f.path))}
        def setup_page(**updates) -> bytes:
            page_values = {**values, **updates}
            return re.sub(r"__([A-Z]+)__", lambda m: page_values[m[1]], template).encode("utf-8")

    class SetupHandler(BaseHTTPRequestHandler):
        def setup(self) -> None:
            self.request.settimeout(10)
            super().setup()

        def log_message(self, format: str, *args) -> None:
            pass

        def respond(self, body: bytes, status: int = 200, content_type: str = "text/html") -> None:
            self.send_response(status)
            self.send_header("Content-Type", f"{content_type}; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path in (route + "/purpose", route + "/questions"):
                self.redirect_to_graph()
                return
            if self.path == route:
                if approved_view.is_file():
                    self.respond(approved_view.read_bytes())
                elif result is None:
                    self.respond(setup_page())
                else:
                    report = json.dumps(last_feedback, ensure_ascii=False).replace("</", "<\\/").encode("utf-8")
                    page = result.read_bytes().replace(b"<body>", b"<body data-live-feedback>", 1)
                    self.respond(page.replace(b"/*__FEEDBACK_RESULT__*/null", report, 1))
            else:
                self.send_error(404)

        def do_POST(self) -> None:
            nonlocal result, failure, prepared, last_feedback
            if self.path == route + "/feedback":
                if approved_view.is_file():
                    self.feedback_response(409, message="이미 최종 승인된 위키예요.")
                elif result is not None:
                    self.apply_feedback()
                else:
                    self.send_error(404)
                return
            if self.path == route + "/approve" and (result is not None or approved_view.is_file()):
                self.approve()
                return
            if self.path not in (route, route + "/questions", route + "/purpose"):
                self.send_error(404)
                return
            if result is not None or approved_view.is_file():
                self.redirect_to_graph()
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BODY:
                    raise ValueError("invalid form size")
                if self.headers.get_content_type() != "application/x-www-form-urlencoded":
                    raise ValueError("invalid form type")
                data = parse_qs(self.rfile.read(length).decode("ascii"), encoding="utf-8", errors="strict",
                                keep_blank_values=True, max_num_fields=len(allowed_fields))
                expected = fields if self.path == route else ("purpose",)
                if (not set(expected) <= set(data) <= allowed_fields
                        or any(len(v) != 1 or len(v[0]) > MAX_ANSWER for v in data.values())):
                    raise ValueError("invalid answers")
                purpose = data["purpose"][0].strip() or "프로젝트 이해"
                if self.path != route:
                    if self.path.endswith("/purpose"):
                        self.respond(setup_page(PURPOSE=escape(purpose)))
                        return
                    questions = [f"‘{purpose}’ 위키에서 {Path(a['path']).name}와 {Path(b['path']).name}를 함께 볼까요?"
                                 for a, b in cards]
                    notice = ""
                    summaries = {}
                    if use_codex and cards:
                        try:
                            questions, summaries = codex_questions(purpose, cards)
                            notice = "질문을 눌러 두 파일을 살펴보고 답을 골라 주세요."
                        except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
                            log.warning("Codex setup questions unavailable: %s", exc)
                            notice = "Codex 응답을 받지 못해 기본 질문을 표시했어요."
                    self.respond(setup_page(PURPOSE=escape(purpose), STAGE="pairs", PAIRS=pair_questions(cards, questions, summaries),
                                            DISPLAYPURPOSE=escape(purpose), NOTICE=notice))
                    return
                initial = pair_feedback(pairs, [data[f"pair{i}"][0] for i in range(len(pairs))],
                                        [data.get(f"direction{i}", [""])[0] for i in range(len(pairs))])
            except (ValueError, TimeoutError):
                self.send_error(400, "Invalid setup form")
                return

            try:
                built = pipeline.build_prepared(prepared, out, cfg, replace(prefs, purpose=purpose), initial)
                result = built["view"]
                last_feedback = built.get("initial_changes")
                prepared = None
            except (Exception, SystemExit) as exc:
                failure = exc
                self.respond("<p>그래프를 만들지 못했습니다. 실행한 터미널에서 오류를 확인해 주세요.</p>".encode("utf-8"),
                             status=500)
            else:
                print(f"viewer: {result}", flush=True)
                self.redirect_to_graph()

        def redirect_to_graph(self) -> None:
            self.send_response(303)
            self.send_header("Location", route)
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def feedback_response(self, status: int, **payload) -> None:
            self.respond(json.dumps(payload, ensure_ascii=False).encode("utf-8"), status, "application/json")

        def read_json(self, limit: int) -> dict:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= limit or self.headers.get_content_type() != "application/json":
                raise ValueError("invalid JSON payload")
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("invalid JSON object")
            return data

        def approve(self) -> None:
            try:
                revision = self.read_json(1024).get("revision")
                if not isinstance(revision, str) or not re.fullmatch(r"[a-f0-9]{64}", revision):
                    raise ValueError("invalid graph revision")
            except (ValueError, TimeoutError):
                self.feedback_response(400, message="승인할 그래프를 확인해 주세요.")
                return
            try:
                approve_wiki(out, cfg, revision, last_feedback)
            except StaleGraphError as exc:
                self.feedback_response(409, message=str(exc))
            except Exception:
                log.exception("Could not approve wiki")
                self.feedback_response(500, message="위키를 확정하지 못했어요. 실행한 터미널을 확인해 주세요.")
            else:
                self.feedback_response(200, approved=True)

        def apply_feedback(self) -> None:
            nonlocal last_feedback
            try:
                data = self.read_json(MAX_FEEDBACK_BODY)
                items = data.get("events")
                if (not isinstance(items, list) or len(items) > 500 or any(not isinstance(e, dict) for e in items)
                        or data.get("text", "") != ""):
                    raise ValueError("expected structured feedback")
            except (ValueError, TimeoutError):
                self.feedback_response(400, message="입력 길이와 피드백을 확인해 주세요.")
                return

            try:
                record = Record.load(out)
                current = final_graph_from_dict(json.loads((out / "final_graph.json").read_text(encoding="utf-8")))
                existing = {edge.id for edge in current.edges}
                events = validate_events(items, record, existing)
                if any(ev.type.startswith("group_") for ev in events):
                    if data.get("revision") != current.revision():
                        self.feedback_response(409, message="그룹 구성이 바뀌었어요. 새로고침 후 그룹 요청을 다시 확인해 주세요.")
                        return
                    names = {g.id: g.name for g in current.groups}
                    for ev in events:
                        if ev.type == "group_add":
                            if ev.group in names or ev.note in names.values() or ev.note == "그룹 없음":
                                raise FeedbackInputError("이미 사용 중인 그룹 이름이나 ID입니다.")
                            names[ev.group] = ev.note
                        elif ev.type == "group_delete":
                            if ev.group not in names:
                                raise FeedbackInputError("삭제할 그룹을 찾지 못했어요.")
                            ev.note = names.pop(ev.group)
                if not events:
                    raise FeedbackInputError("반영할 피드백을 추가해 주세요.")
                updated = pipeline.correct(out, cfg, record=record, new_feedback=events)["graph"]
                last_feedback = feedback_changes(current, updated, events, cfg.corrector)
            except FeedbackInputError as exc:
                self.feedback_response(422, message=str(exc))
            except (Exception, SystemExit):
                log.exception("Could not apply feedback")
                self.feedback_response(500, message="피드백을 반영하지 못했어요. 실행한 터미널을 확인해 주세요.")
            else:
                self.feedback_response(200, applied=len(events))

    with HTTPServer(("127.0.0.1", 0), SetupHandler) as server:
        url = f"http://127.0.0.1:{server.server_port}{route}"
        print(f"위키 설정: {url}", flush=True)
        webbrowser.open(url)
        print("피드백을 반영하는 동안 터미널을 열어 두세요. 종료하려면 Ctrl+C를 누르세요.", flush=True)
        try:
            while failure is None:
                server.handle_request()
        except KeyboardInterrupt:
            return

    if failure is not None:
        raise failure
