"""Unit tests for the TAEW-DP core algorithm."""

import pytest

from trackslim.core import Simplifier, Track, TrackPoint, turn_angle_deg


def make_track(coords, name="test"):
    points = [
        TrackPoint(lat=lat, lon=lon, ele=ele, time=None)
        for lat, lon, ele in coords
    ]
    return Track(points=points, name=name)


def straight_coords(n=10, ele=50.0):
    # Points march north in equal steps at constant elevation.
    return [(37.5 + i * 0.0001, 127.0, ele) for i in range(n)]


def test_straight_line_collapses_to_two_points():
    track = make_track(straight_coords(10))
    result = Simplifier(tolerance_m=5.0).simplify(track)
    assert len(result.points) == 2
    assert result.points[0].lat == pytest.approx(37.5)
    assert result.points[-1].lat == pytest.approx(37.5 + 9 * 0.0001)


def test_straight_line_turn_angle_is_near_zero():
    a = TrackPoint(lat=37.5000, lon=127.0, ele=50.0, time=None)
    b = TrackPoint(lat=37.5010, lon=127.0, ele=50.0, time=None)
    c = TrackPoint(lat=37.5020, lon=127.0, ele=50.0, time=None)
    assert turn_angle_deg(a, b, c) == pytest.approx(0.0, abs=1.0)


def test_sharp_turn_is_kept():
    # North for about 110 m, then east for about 90 m: a right-angle corner.
    track = make_track([
        (37.5000, 127.0000, 50.0),
        (37.5010, 127.0000, 50.0),
        (37.5010, 127.0010, 50.0),
    ])
    corner = track.points
    angle = turn_angle_deg(corner[0], corner[1], corner[2])
    assert angle == pytest.approx(90.0, abs=1.0)

    result = Simplifier(tolerance_m=5.0, min_turn_deg=35.0).simplify(track)
    assert len(result.points) == 3
    assert result.points[1].lat == pytest.approx(37.5010)


def test_elevation_spike_kept():
    coords = straight_coords(7, ele=50.0)
    lat, lon, _ = coords[3]
    coords[3] = (lat, lon, 200.0)  # a 150 m spike in the middle of a flat line
    track = make_track(coords)

    result = Simplifier(tolerance_m=5.0, elev_weight=0.5).simplify(track)
    assert any(p.ele == 200.0 for p in result.points)


def test_compression_ratio_value():
    original = make_track(straight_coords(10)).points
    simplified = original[::3]  # keeps indices 0, 3, 6, 9 -> 4 points
    assert len(simplified) == 4
    ratio = 1 - len(simplified) / len(original)
    assert ratio == pytest.approx(0.6)


def test_simplify_returns_track_with_same_name():
    track = make_track(straight_coords(5), name="morning_run")
    result = Simplifier(tolerance_m=5.0).simplify(track)
    assert isinstance(result, Track)
    assert result.name == "morning_run"
