"""Unit tests for GPX reading and writing."""
from datetime import timedelta

import pytest

from trackslim.io import read_gpx, write_gpx, parse_time
from trackslim import Track, TrackPoint

GPX_NS = "http://www.topografix.com/GPX/1/1"

SEG_A = [(37.5000, 127.0000, 50), (37.5010, 127.0010, 55), (37.5020, 127.0020, 60)]
SEG_B = [(37.5030, 127.0030, 62), (37.5040, 127.0040, 65), (37.5050, 127.0050, 70)]


def _gpx(segments):
    """Build a GPX 1.1 document from a list of segments of (lat, lon, ele) tuples."""
    counter = 0
    trksegs = []
    for seg in segments:
        pts = []
        for lat, lon, ele in seg:
            pts.append(
                f'<trkpt lat="{lat}" lon="{lon}"><ele>{ele}</ele>'
                f"<time>2026-09-02T10:00:{counter:02d}Z</time></trkpt>"
            )
            counter += 1
        trksegs.append("<trkseg>" + "".join(pts) + "</trkseg>")
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<gpx version="1.1" creator="test" xmlns="{GPX_NS}">'
        "<trk><name>sample</name>" + "".join(trksegs) + "</trk></gpx>"
    )


def test_roundtrip(tmp_path):
    t1 = parse_time("2026-09-02T10:00:00Z")
    t2 = parse_time("2026-09-02T10:00:05Z")
    track = Track(
        points=[
            TrackPoint(lat=37.5, lon=127.0, ele=50.0, time=t1),
            TrackPoint(lat=37.501, lon=127.001, ele=55.5, time=t2),
        ],
        name="roundtrip",
    )
    path = tmp_path / "rt.gpx"
    write_gpx(track, path)

    loaded = read_gpx(path)

    assert len(loaded.points) == 2
    for original, back in zip(track.points, loaded.points):
        assert back.lat == pytest.approx(original.lat)
        assert back.lon == pytest.approx(original.lon)
        assert back.ele == pytest.approx(original.ele)
        assert back.time == original.time


def test_missing_ele_defaults_zero(tmp_path):
    path = tmp_path / "no_ele.gpx"
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<gpx version="1.1" creator="test" xmlns="{GPX_NS}">'
        "<trk><trkseg>"
        '<trkpt lat="37.5" lon="127.0"><time>2026-09-02T10:00:00Z</time></trkpt>'
        "</trkseg></trk></gpx>",
        encoding="utf-8",
    )

    with pytest.warns(UserWarning):
        track = read_gpx(path)

    assert len(track.points) == 1
    assert track.points[0].ele == 0.0


def test_parse_time_z():
    t = parse_time("2026-09-02T10:00:00Z")

    assert (t.year, t.month, t.day, t.hour) == (2026, 9, 2, 10)
    assert t.utcoffset() == timedelta(0)


def test_multi_segment_keeps_last_point(tmp_path):
    # Regression test for bug report #37: the final point of every
    # segment after the first was being dropped.
    path = tmp_path / "two_segments.gpx"
    path.write_text(_gpx([SEG_A, SEG_B]), encoding="utf-8")

    track = read_gpx(path)

    assert len(track.points) == 6
    lats = [p.lat for p in track.points]
    assert lats[0] == pytest.approx(37.5000)
    assert lats[2] == pytest.approx(37.5020)
    assert lats[3] == pytest.approx(37.5030)
    assert lats[-1] == pytest.approx(37.5050)
