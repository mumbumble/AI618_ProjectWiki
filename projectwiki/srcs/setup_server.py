"""Collect initial preferences and serve the graph with live feedback on loopback."""
from __future__ import annotations

import json
import logging
import re
import secrets
import webbrowser
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from .. import pipeline
from ..config import Config
from ..schema import Graph, Preferences
from .feedback_changes import feedback_changes
from .initial_preferences import preferences_from_answers
from .record import Record
from .text_feedback import FeedbackInputError, interpret, validate_events
from .wiki_approval import APPROVED_DIR, StaleGraphError, approve_wiki


FORM = Path(__file__).with_name("setup_form.html")
FIELDS = ("purpose", "priority", "grouping")
MAX_ANSWER = 1000
# Browser form encoding can take three ASCII characters per byte of UTF-8.
MAX_BODY = len(FIELDS) * MAX_ANSWER * 12 + 128
MAX_FEEDBACK_BODY = 256_000
log = logging.getLogger(__name__)


def run_setup(root: Path, out: Path, cfg: Config, prefs: Preferences) -> None:
    values = {"PURPOSE": prefs.purpose, "PRIORITY": prefs.guide.get("priority_materials", ""),
              "GROUPING": prefs.guide.get("grouping_request", "")}
    form = re.sub(r"__(PURPOSE|PRIORITY|GROUPING)__", lambda match: escape(values[match[1]]),
                  FORM.read_text(encoding="utf-8")).encode("utf-8")
    route = "/" + secrets.token_urlsafe(24)
    result: Path | None = None
    failure: Exception | SystemExit | None = None
    last_feedback: dict | None = None
    approved_view = out / APPROVED_DIR / "view.html"

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
            if self.path == route:
                if approved_view.is_file():
                    self.respond(approved_view.read_bytes())
                elif result is None:
                    self.respond(form)
                else:
                    report = json.dumps(last_feedback, ensure_ascii=False).replace("</", "<\\/").encode("utf-8")
                    page = result.read_bytes().replace(b"<body>", b"<body data-live-feedback>", 1)
                    self.respond(page.replace(b"/*__FEEDBACK_RESULT__*/null", report, 1))
            else:
                self.send_error(404)

        def do_POST(self) -> None:
            nonlocal result, failure
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
            if self.path != route:
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
                                keep_blank_values=True, max_num_fields=len(FIELDS))
                if set(data) != set(FIELDS) or any(len(v) != 1 or len(v[0]) > MAX_ANSWER for v in data.values()):
                    raise ValueError("invalid answers")
                answers = [data[field][0].strip() for field in FIELDS]
            except (ValueError, TimeoutError):
                self.send_error(400, "Invalid setup form")
                return

            try:
                result = pipeline.build(root, out, cfg, preferences_from_answers(prefs, *answers))["view"]
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
                items, request = data.get("events"), data.get("text")
                if (not isinstance(items, list) or len(items) > 500 or any(not isinstance(e, dict) for e in items)
                        or not isinstance(request, str) or len(request) > MAX_ANSWER):
                    raise ValueError("invalid events or text")
                request = request.strip()
            except (ValueError, TimeoutError):
                self.feedback_response(400, message="입력 길이와 피드백을 확인해 주세요.")
                return

            try:
                record = Record.load(out)
                current = Graph.from_dict(json.loads((out / "final_graph.json").read_text(encoding="utf-8")))
                existing = {edge.id for edge in current.edges}
                events = validate_events(items, record, existing)
                if request:
                    if not cfg.llm:
                        raise FeedbackInputError("자유 텍스트를 해석하려면 Claude가 필요해요. --no-llm 없이 실행해 주세요.")
                    llm = pipeline.make_llm(cfg, out)
                    assert llm is not None
                    try:
                        parsed = interpret(request, record, [g.name for g in current.groups], llm, cfg)
                    finally:
                        llm.save()
                    events.extend(validate_events(parsed, record, existing, request=request))
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
