"""Pretrained models used by the pipeline.

- encoders.py   bge-m3 dense encoder (stage 2), TF-IDF stand-in for tests
- reranker.py   bge-reranker-v2-m3 cross-encoder (stage 5 evidence pairs)
- claude.py     Claude calls with JSON-schema outputs, cache and cost report (stages 3-5)
- claude_cli.py Claude Code CLI backend: the logged-in subscription account instead of an API key
"""
from .claude import PRICES, Claude, obj_schema
from .claude_cli import ClaudeCodeClient, find_claude
from .encoders import BgeM3Encoder, TfidfEncoder, make_encoder
from .reranker import Reranker

__all__ = ["PRICES", "BgeM3Encoder", "Claude", "ClaudeCodeClient", "Reranker", "TfidfEncoder", "find_claude",
           "make_encoder", "obj_schema"]
