"""`projectlens doctor`: check the environment before a real run."""
from __future__ import annotations

import importlib
import os
import sys

from .config import Config

PACKAGES = ["numpy", "sklearn", "pymupdf", "transformers", "huggingface_hub", "anthropic"]


def _line(ok: bool, text: str) -> bool:
    print(f"[{'ok' if ok else '!!'}] {text}")
    return ok


def run() -> int:
    cfg = Config()
    good = _line(sys.version_info >= (3, 10), f"python {sys.version.split()[0]}")
    for name in PACKAGES:
        try:
            mod = importlib.import_module(name)
            _line(True, f"{name} {getattr(mod, '__version__', '')}")
        except ImportError as e:
            good = _line(False, f"{name} missing ({e}); pip install -r requirements.txt")

    try:
        import torch
        tv = tuple(int(x) for x in torch.__version__.split("+")[0].split(".")[:2])
        good &= _line(tv >= (2, 6), f"torch {torch.__version__} (transformers 5.x needs >= 2.6)")
        if torch.cuda.is_available():
            _line(True, f"GPU: {torch.cuda.get_device_name(0)} (CUDA {torch.version.cuda})")
        elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            _line(True, "GPU: Apple MPS")
        else:
            _line(False, "no GPU: bge-m3 and the reranker run on CPU (slow on large folders)")
    except ImportError:
        good = _line(False, "torch missing; see requirements.txt for the install command")

    try:
        from huggingface_hub import snapshot_download
        for name in (cfg.encoder_model, cfg.reranker):
            try:
                snapshot_download(name, local_files_only=True, allow_patterns=["*.json"])
                _line(True, f"model cached: {name}")
            except Exception:
                good = _line(False, f"model not cached: {name}; run python scripts/download_models.py")
    except ImportError:
        pass

    key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    _line(key, "ANTHROPIC_API_KEY " + ("set" if key else "not set: Claude stages need it (or run with --no-llm)"))
    print("ready" if good and key else "ready for --no-llm runs" if good else "fix the items marked !!")
    return 0 if good else 1
