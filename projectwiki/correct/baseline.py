"""Control condition for stage 6: feedback is not generalized; only the explicit edits apply (stage 7)."""
from __future__ import annotations

from ..config import Config
from ..record import Record
from ..schema import FeedbackEvent, Graph
from .base import Correction


class BaselineCorrector:
    name = "baseline"

    def __init__(self, cfg: Config):
        pass

    def correct(self, graph: Graph, feedback: list[FeedbackEvent], record: Record) -> Correction:
        return Correction(notes=[f"{len(feedback)} feedback events, none generalized"])
