import base64
import json
import stat
import sys

import pytest

from projectwiki.srcs.claude_cli import ClaudeCodeClient

FAKE = r'''#!PYTHON
import json, sys
args = sys.argv[1:]
schema = json.loads(args[args.index("--json-schema") + 1])
prompt = sys.stdin.read()
tools = args[args.index("--tools") + 1]
out = {}
for k, v in schema["properties"].items():
    out[k] = v["enum"][0] if "enum" in v else True if v["type"] == "boolean" else f"{k}:{tools}:{len(prompt)}"
print(json.dumps({"type": "result", "is_error": False, "structured_output": out, "total_cost_usd": 0.01,
                  "usage": {"input_tokens": 3, "cache_read_input_tokens": 100, "output_tokens": 7}}))
'''


@pytest.fixture
def fake_claude(tmp_path):
    path = tmp_path / "claude"
    path.write_text(FAKE.replace("PYTHON", sys.executable), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


@pytest.mark.skipif(sys.platform == "win32", reason="the fake CLI is a shebang script")
def test_text_request(fake_claude):
    schema = {"type": "object", "properties": {"summary": {"type": "string"}, "keep": {"type": "boolean"},
                                               "relation": {"type": "string", "enum": ["uses", "other"]}}}
    resp = ClaudeCodeClient(binary=fake_claude).messages.create(
        model="claude-haiku-5-5", max_tokens=100, system="sys", messages=[{"role": "user", "content": "hello"}],
        output_config={"format": {"type": "json_schema", "schema": schema}})
    data = json.loads(resp.content[0].text)
    assert data == {"summary": "summary::5", "keep": True, "relation": "uses"}
    assert resp.usage.input_tokens == 103 and resp.cost_usd == 0.01


@pytest.mark.skipif(sys.platform == "win32", reason="the fake CLI is a shebang script")
def test_image_request_enables_read(fake_claude):
    png = base64.b64encode(b"\x89PNG fake").decode()
    content = [{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": png}},
               {"type": "text", "text": "Path: fig.png"}]
    schema = {"type": "object", "properties": {"description": {"type": "string"}}}
    resp = ClaudeCodeClient(binary=fake_claude).messages.create(
        model="claude-sonnet-5-5", max_tokens=100, system="sys", messages=[{"role": "user", "content": content}],
        output_config={"format": {"type": "json_schema", "schema": schema}})
    assert json.loads(resp.content[0].text)["description"].startswith("description:Read:")
