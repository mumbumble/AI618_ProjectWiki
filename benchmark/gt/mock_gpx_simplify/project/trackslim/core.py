"""Core simplification algorithm for trackslim.

The simplifier is a Douglas-Peucker variant (Turn-Aware Elevation-Weighted
Douglas-Peucker, TAEW-DP). Besides horizontal distance it adds an elevation
term and a turn term, so switchbacks and climbs survive simplification.
"""

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple

EARTH_RADIUS_M = 6371000.0


@dataclass(frozen=True)
class TrackPoint:
    lat: float
    lon: float
    ele: float = 0.0
    time: Optional[datetime] = None


@dataclass(frozen=True)
class Track:
    points: Tuple[TrackPoint, ...]
    name: str = ""

    def __post_init__(self):
        object.__setattr__(self, "points", tuple(self.points))

    def __len__(self):
        return len(self.points)


def _to_xy(p, ref_lat):
    """Equirectangular projection to metres around ref_lat."""
    x = math.radians(p.lon) * math.cos(math.radians(ref_lat)) * EARTH_RADIUS_M
    y = math.radians(p.lat) * EARTH_RADIUS_M
    return x, y


def _project(p, a, b):
    """Return (horizontal distance in metres, fractional position on a-b)."""
    px, py = _to_xy(p, a.lat)
    ax, ay = _to_xy(a, a.lat)
    bx, by = _to_xy(b, a.lat)
    dx, dy = bx - ax, by - ay
    seg_len2 = dx * dx + dy * dy
    if seg_len2 == 0.0:
        return math.hypot(px - ax, py - ay), 0.0
    t = ((px - ax) * dx + (py - ay) * dy) / seg_len2
    t = max(0.0, min(1.0, t))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy)), t


def perpendicular_distance_m(p, a, b):
    """Horizontal distance in metres from p to the segment a-b."""
    return _project(p, a, b)[0]


def turn_angle_deg(a, b, c):
    """Heading change at b when travelling a -> b -> c (0 = straight)."""
    ax, ay = _to_xy(a, b.lat)
    bx, by = _to_xy(b, b.lat)
    cx, cy = _to_xy(c, b.lat)
    v1x, v1y = bx - ax, by - ay
    v2x, v2y = cx - bx, cy - by
    cross = v1x * v2y - v1y * v2x
    dot = v1x * v2x + v1y * v2y
    return abs(math.degrees(math.atan2(cross, dot)))


def weighted_error(p, a, b, turn_weight=2.0, elev_weight=0.5, tolerance_m=5.0):
    """Error of point p against the chord a-b, in metres-equivalent units."""
    dist, t = _project(p, a, b)
    expected_ele = a.ele + t * (b.ele - a.ele)
    vertical = abs(p.ele - expected_ele)
    turn = turn_angle_deg(a, p, b)
    return dist + elev_weight * vertical + turn_weight * (turn / 180.0) * tolerance_m


class Simplifier:
    """Turn-aware, elevation-weighted Douglas-Peucker simplifier."""

    def __init__(self, tolerance_m=5.0, turn_weight=2.0, elev_weight=0.5, min_turn_deg=35.0):
        if tolerance_m <= 0:
            raise ValueError("tolerance_m must be positive")
        self.tolerance_m = float(tolerance_m)
        self.turn_weight = float(turn_weight)
        self.elev_weight = float(elev_weight)
        self.min_turn_deg = float(min_turn_deg)

    def _error(self, p, a, b):
        return weighted_error(
            p, a, b,
            turn_weight=self.turn_weight,
            elev_weight=self.elev_weight,
            tolerance_m=self.tolerance_m,
        )

    def _forced_indices(self, pts):
        """Interior points whose turn is sharp enough to be always kept."""
        forced = set()
        for i in range(1, len(pts) - 1):
            if turn_angle_deg(pts[i - 1], pts[i], pts[i + 1]) >= self.min_turn_deg:
                forced.add(i)
        return forced

    def simplify(self, track):
        pts = list(track.points)
        n = len(pts)
        if n <= 2:
            return Track(tuple(pts), track.name)

        forced = self._forced_indices(pts)
        keep = [False] * n
        keep[0] = keep[-1] = True
        stack = [(0, n - 1)]  # iterative stack instead of recursion

        while stack:
            i, j = stack.pop()
            if j - i < 2:
                continue
            best_k, best_e = None, -1.0
            forced_k, forced_e = None, -1.0
            for k in range(i + 1, j):
                e = self._error(pts[k], pts[i], pts[j])
                if e > best_e:
                    best_k, best_e = k, e
                if k in forced and e > forced_e:
                    forced_k, forced_e = k, e
            if forced_k is not None:
                split = forced_k
            elif best_e > self.tolerance_m:
                split = best_k
            else:
                continue
            keep[split] = True
            stack.append((i, split))
            stack.append((split, j))

        return Track(tuple(p for p, k in zip(pts, keep) if k), track.name)


def simplify_track(track, tolerance_m=5.0, turn_weight=2.0, elev_weight=0.5):
    """Convenience wrapper around Simplifier with default min_turn_deg."""
    simplifier = Simplifier(
        tolerance_m=tolerance_m,
        turn_weight=turn_weight,
        elev_weight=elev_weight,
    )
    return simplifier.simplify(track)


def compression_ratio(original, simplified):
    """Fraction of points removed: 1 - len(simplified) / len(original)."""
    if len(original) == 0:
        return 0.0
    return 1.0 - len(simplified) / len(original)
