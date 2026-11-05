from __future__ import annotations

from typing import Protocol

from ..stage3_record import Record
from ..schema import Group, Preferences


class Clusterer(Protocol):
    """Groups may leave out files (ungrouped nodes). Group names are filled in later when empty."""
    name: str

    def cluster(self, record: Record, prefs: Preferences) -> list[Group]: ...
