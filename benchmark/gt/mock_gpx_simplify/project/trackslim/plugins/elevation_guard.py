"""Elevation guard plugin for trackslim.

Plugins live in ``trackslim.plugins``. Each module subclasses ``Simplifier``
and is selected either from the command line with ``--plugin elevation_guard``
or by importing the class directly::

    from trackslim.plugins.elevation_guard import ElevationGuardSimplifier

The plain simplifier can flatten short climbs, which leaves the total ascent
of a hiking track wrong. This plugin runs the regular simplification first and
then re-inserts original points wherever the cumulative climb of the simplified
track drifts from the original by more than ``max_ele_error_m`` metres.
"""

from trackslim.core import Simplifier, Track

PLUGIN_NAME = "elevation_guard"


def _ascent(points, i, j):
    """Total climb across the original points i..j (inclusive)."""
    total = 0.0
    for k in range(i + 1, j + 1):
        delta = points[k].ele - points[k - 1].ele
        if delta > 0:
            total += delta
    return total


class ElevationGuardSimplifier(Simplifier):
    """Simplifier that keeps the total ascent within ``max_ele_error_m``."""

    def __init__(self, tolerance_m=5.0, turn_weight=2.0, elev_weight=0.5,
                 min_turn_deg=35.0, max_ele_error_m=3.0):
        super().__init__(
            tolerance_m=tolerance_m,
            turn_weight=turn_weight,
            elev_weight=elev_weight,
            min_turn_deg=min_turn_deg,
        )
        self.max_ele_error_m = max_ele_error_m

    def simplify(self, track):
        base = super().simplify(track)
        original = list(track.points)
        if len(original) < 3:
            return base
        kept = self._map_indices(original, base.points)
        kept = self._refine(original, kept)
        return Track(points=[original[k] for k in kept], name=track.name)

    @staticmethod
    def _map_indices(original, simplified):
        """Translate simplified points back to their indices in the original."""
        indices = []
        pos = 0
        for pt in simplified:
            while pos < len(original) and original[pos] != pt:
                pos += 1
            indices.append(pos)
            pos += 1
        return indices

    def _refine(self, points, kept):
        """Add points to any span whose climb error exceeds the limit."""
        result = set(kept)
        stack = list(zip(kept, kept[1:]))
        while stack:
            i, j = stack.pop()
            if j - i < 2:
                continue
            true_climb = _ascent(points, i, j)
            simple_climb = max(0.0, points[j].ele - points[i].ele)
            if abs(true_climb - simple_climb) <= self.max_ele_error_m:
                continue
            m = self._worst_point(points, i, j)
            result.add(m)
            stack.append((i, m))
            stack.append((m, j))
        return sorted(result)

    @staticmethod
    def _worst_point(points, i, j):
        """Index whose running climb deviates most from a linear share."""
        total = _ascent(points, i, j)
        best, best_gap, run = i + 1, -1.0, 0.0
        for k in range(i + 1, j):
            delta = points[k].ele - points[k - 1].ele
            if delta > 0:
                run += delta
            share = total * (k - i) / (j - i)
            gap = abs(run - share)
            if gap > best_gap:
                best, best_gap = k, gap
        return best
