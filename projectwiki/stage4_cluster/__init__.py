"""Stage 4, experimental slot: group files, optionally using the user's preferences.

A method is a class built as `Method(cfg)` with `cluster(record, prefs) -> list[Group]`.
Register it in CLUSTERERS, or pass `--clusterer package.module:Method`.
"""
from ..config import Config
from ..plugins import load_component
from .base import Clusterer
from .baseline import BaselineClusterer
from .naming import name_groups
from .preference import PreferenceClusterer

CLUSTERERS = {"baseline": BaselineClusterer, "pref": PreferenceClusterer}


def get_clusterer(name: str, cfg: Config) -> Clusterer:
    return load_component(name, CLUSTERERS, cfg)


__all__ = ["CLUSTERERS", "Clusterer", "BaselineClusterer", "PreferenceClusterer", "get_clusterer", "name_groups"]
