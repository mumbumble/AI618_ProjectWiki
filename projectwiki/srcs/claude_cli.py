"""Claude Code CLI as the LLM backend (`--llm-backend cli`).

Runs `claude -p --json-schema ...` for each request, so it uses the logged-in Claude Code account instead of
an API key. Meant for testing: every call starts a CLI process (about 5 s) and carries the CLI's own prompt
overhead. The object mimics `anthropic.Anthropic().messages.create` closely enough for `llm.Claude`.
"""
from __future__ import annotations

import base64
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace


def find_claude() -> str | None:
    found = shutil.which("claude")
    if found:
        return found
    local = Path.home() / ".local" / "bin" / "claude"
    return str(local) if local.exists() else None


class ClaudeCodeClient:
    def __init__(self, binary: str | None = None, timeout: int = 600):
        self.binary = binary or find_claude()
        if not self.binary:
            raise SystemExit("claude CLI not found. Install Claude Code and log in, or use --llm-backend api.")
        self.timeout = timeout
        self.messages = self

    def create(self, model: str, max_tokens: int, system: str, messages: list, output_config: dict):
        schema = output_config["format"]["schema"]
        content = messages[0]["content"]
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content
        with tempfile.TemporaryDirectory(prefix="projectwiki_") as tmp:
            parts, tools = [], ""
            for i, block in enumerate(blocks):
                if block["type"] == "text":
                    parts.append(block["text"])
                elif block["type"] == "image":  # the CLI reads images from disk with its Read tool
                    path = Path(tmp) / f"image_{i}.png"
                    path.write_bytes(base64.b64decode(block["source"]["data"]))
                    parts.append(f"Open the image file {path} with the Read tool and answer about it.")
                    tools = "Read"
            cmd = [self.binary, "-p", "--model", model, "--output-format", "json", "--no-session-persistence",
                   "--setting-sources", "", "--system-prompt", system, "--json-schema", json.dumps(schema),
                   "--tools", tools]
            if tools:
                cmd += ["--allowedTools", tools]
            res = subprocess.run(cmd, input="\n\n".join(parts), capture_output=True, text=True,
                                 timeout=self.timeout, cwd=tmp)
        try:
            data = json.loads(res.stdout)
        except json.JSONDecodeError:
            raise RuntimeError(f"claude CLI exited {res.returncode}: {(res.stderr or res.stdout)[-300:]}") from None
        if data.get("is_error") or data.get("structured_output") is None:
            raise RuntimeError(f"claude CLI returned no structured output: {str(data.get('result'))[:300]}")
        usage = data.get("usage") or {}
        tokens_in = sum(usage.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens",
                                                  "cache_read_input_tokens"))
        return SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text=json.dumps(data["structured_output"], ensure_ascii=False))],
            usage=SimpleNamespace(input_tokens=tokens_in, output_tokens=usage.get("output_tokens", 0)),
            cost_usd=data.get("total_cost_usd"),
        )
