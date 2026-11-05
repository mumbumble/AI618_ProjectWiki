from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..stage3_record import Record
from ..schema import Edge, FeedbackEvent, Graph


@dataclass
class Correction:
    edge_scores: dict[str, float] = field(default_factory=dict)  # edge id -> new score
    hide: list[str] = field(default_factory=list)  # edge ids the method drops
    new_edges: list[Edge] = field(default_factory=list)  # edges the method proposes
    node_groups: dict[str, str | None] = field(default_factory=dict)  # file id -> group id it proposes
    explanations: dict[str, str] = field(default_factory=dict)  # edge id -> reason shown to the user
    notes: list[str] = field(default_factory=list)


class Corrector(Protocol):
    name: str

    def correct(self, graph: Graph, feedback: list[FeedbackEvent], record: Record) -> Correction: ...
