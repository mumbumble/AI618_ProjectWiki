"""Claude calls with JSON-schema outputs, an on-disk cache and token accounting."""
from __future__ import annotations

import hashlib
import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..config import Config

log = logging.getLogger(__name__)

# $ per million input / output tokens, prompts up to 100K tokens
PRICES = {"claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}


def obj_schema(**props) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


class Claude:
    def __init__(self, cfg: Config, cache_path: Path, client=None):
        if client is None:
            import anthropic
            client = anthropic.Anthropic(max_retries=4)
        self.client = client
        self.effort, self.workers = cfg.llm_effort, cfg.llm_workers
        self.cache_path = cache_path
        self.cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
        self.usage: dict[str, list[float]] = {}  # model -> [calls, input tokens, output tokens, reported $]
        self.lock = threading.Lock()

    def json(self, model: str, system: str, content, schema: dict, key: str, max_tokens: int = 4000):
        """Return the parsed JSON answer, or None when the call fails. `key` identifies the input for caching."""
        k = hashlib.sha1(json.dumps([model, system, schema, key], ensure_ascii=False).encode()).hexdigest()
        if k in self.cache:
            return self.cache[k]
        try:
            resp = self.client.messages.create(
                model=model, max_tokens=max_tokens, system=system,
                messages=[{"role": "user", "content": content}],
                output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": schema}},
            )
        except Exception as e:  # anthropic.APIError and network errors: skip this item, keep the run going
            log.warning("%s call failed: %s", model, e)
            return None
        if resp.stop_reason in ("refusal", "max_tokens"):
            log.warning("%s stopped with %s", model, resp.stop_reason)
            return None
        text = next((b.text for b in resp.content if b.type == "text"), None)
        try:
            data = json.loads(text)
        except (TypeError, json.JSONDecodeError):
            log.warning("%s returned no JSON", model)
            return None
        with self.lock:
            self.cache[k] = data
            u = self.usage.setdefault(model, [0, 0, 0, 0.0])
            u[0] += 1
            u[1] += resp.usage.input_tokens
            u[2] += resp.usage.output_tokens
            u[3] += getattr(resp, "cost_usd", None) or 0.0  # the CLI backend reports its own cost
        return data

    def map(self, fn, items: list) -> list:
        with ThreadPoolExecutor(self.workers) as ex:
            out = list(ex.map(fn, items))
        self.save()
        return out

    def save(self) -> None:
        with self.lock:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self.cache, ensure_ascii=False), encoding="utf-8")

    def cost_report(self) -> str:
        parts, total = [], 0.0
        for model, (n, i, o, reported) in self.usage.items():
            pin, pout = PRICES.get(model, (0.0, 0.0))
            cost = reported or i / 1e6 * pin + o / 1e6 * pout
            total += cost
            parts.append(f"{model}: {n} calls, in {i:,} / out {o:,} tok (${cost:.3f})")
        return "; ".join(parts) + f"; total ${total:.3f}" if parts else "no new LLM calls (all cached)"
