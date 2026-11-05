"""Stage 6, experimental slot: generalize the user's feedback to the rest of the graph.

A method is a class built as `Method(cfg)` with `correct(graph, feedback, record) -> Correction`.
Explicit edits (delete, add, confirm, move) are always applied afterwards in stage 7, so a method only
decides what the feedback implies for edges and nodes the user did not touch.
Register it in CORRECTORS, or pass `--corrector package.module:Method`.
"""
from ..config import Config
from ..plugins import load_component
from .align import AlignCorrector
from .base import Correction, Corrector
from .baseline import BaselineCorrector
from .drift import DriftCorrector

CORRECTORS = {"baseline": BaselineCorrector, "drift": DriftCorrector, "align": AlignCorrector}


def get_corrector(name: str, cfg: Config) -> Corrector:
    return load_component(name, CORRECTORS, cfg)


__all__ = ["CORRECTORS", "Correction", "Corrector", "AlignCorrector", "BaselineCorrector", "DriftCorrector",
           "get_corrector"]
