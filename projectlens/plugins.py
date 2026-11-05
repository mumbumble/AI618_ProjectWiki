"""Load an experimental-slot method by registry name or by "package.module:ClassName"."""
from __future__ import annotations

from importlib import import_module

from .config import Config


def load_component(name: str, registry: dict, cfg: Config):
    if ":" in name:
        module, cls = name.split(":", 1)
        return getattr(import_module(module), cls)(cfg)
    if name not in registry:
        raise ValueError(f"unknown method {name!r}; registered: {', '.join(registry)} (or use module:Class)")
    return registry[name](cfg)
