"""Open a one-time browser form before building a project's first graph."""
from __future__ import annotations

import re
import secrets
import webbrowser
from collections.abc import Callable
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from ..schema import Preferences
from .initial_preferences import preferences_from_answers


FORM = Path(__file__).with_name("setup_form.html")
FIELDS = ("purpose", "priority", "grouping")
MAX_ANSWER = 1000
# Browser form encoding can take three ASCII characters per byte of UTF-8.
MAX_BODY = len(FIELDS) * MAX_ANSWER * 12 + 128


def run_setup(prefs: Preferences, build: Callable[[Preferences], Path]) -> Path:
    values = {"PURPOSE": prefs.purpose, "PRIORITY": prefs.guide.get("priority_materials", ""),
              "GROUPING": prefs.guide.get("grouping_request", "")}
    form = re.sub(r"__(PURPOSE|PRIORITY|GROUPING)__", lambda match: escape(values[match[1]]),
                  FORM.read_text(encoding="utf-8")).encode("utf-8")
    route = "/" + secrets.token_urlsafe(24)
    result: Path | None = None
    failure: Exception | SystemExit | None = None

    class SetupHandler(BaseHTTPRequestHandler):
        def setup(self) -> None:
            self.request.settimeout(10)
            super().setup()

        def log_message(self, format: str, *args) -> None:
            pass

        def respond(self, body: bytes, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path == route:
                self.respond(form)
            else:
                self.send_error(404)

        def do_POST(self) -> None:
            nonlocal result, failure
            if self.path != route:
                self.send_error(404)
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
                viewer = build(preferences_from_answers(prefs, *answers))
                html = viewer.read_bytes()
            except (Exception, SystemExit) as exc:
                failure = exc
                self.respond("<p>그래프를 만들지 못했습니다. 실행한 터미널에서 오류를 확인해 주세요.</p>".encode("utf-8"),
                             status=500)
            else:
                result = viewer
                self.respond(html)

    with HTTPServer(("127.0.0.1", 0), SetupHandler) as server:
        url = f"http://127.0.0.1:{server.server_port}{route}"
        print(f"위키 설정: {url}", flush=True)
        webbrowser.open(url)
        while result is None and failure is None:
            server.handle_request()

    if failure is not None:
        raise failure
    assert result is not None
    return result
