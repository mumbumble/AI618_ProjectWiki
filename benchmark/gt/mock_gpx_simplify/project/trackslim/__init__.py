"""trackslim: simplify GPS tracks while keeping turns and elevation changes.

trackslim reads GPX 1.1 tracks, reduces the number of points with the
Turn-Aware Elevation-Weighted Douglas-Peucker algorithm (TAEW-DP), and
writes the result back out as GPX. The library uses only the standard
library, so it has no runtime dependencies.

Quick start::

    import trackslim

    track = trackslim.read_gpx("ride.gpx")
    small = trackslim.simplify_track(track, tolerance_m=5.0)
    print(trackslim.compression_ratio(track, small))
    trackslim.write_gpx(small, "ride_small.gpx")

Public API
----------
read_gpx(path) -> Track
    Parse a GPX file. Multiple <trkseg> segments are merged into one Track.
    Timestamps are parsed from ISO-8601, and a missing <ele> becomes 0.0.

write_gpx(track, path)
    Write a Track as GPX 1.1 using <trk><trkseg><trkpt lat lon> elements.

simplify_track(track, tolerance_m=5.0, turn_weight=2.0, elev_weight=0.5) -> Track
    Convenience wrapper around Simplifier. Uses the default min_turn_deg of 35.0.

Simplifier(tolerance_m=5.0, turn_weight=2.0, elev_weight=0.5, min_turn_deg=35.0)
    Simplifier.simplify(track) -> Track.
    The point error is the horizontal perpendicular distance, plus elev_weight
    times the vertical deviation from the interpolated elevation, plus
    turn_weight * (turn angle / 180) * tolerance_m. Any point whose turn angle
    is at least min_turn_deg is always kept.

compression_ratio(original, simplified) -> float
    Returns 1 - len(simplified) / len(original).

TrackPoint(lat, lon, ele, time)
    A single GPS fix. Frozen dataclass.

Track(points, name)
    An ordered collection of TrackPoint objects with an optional name.
    Frozen dataclass.

Version history is available in the project changelog.
"""

from .core import Simplifier, Track, TrackPoint, compression_ratio, simplify_track
from .io import read_gpx, write_gpx

__version__ = "0.4.0"

__all__ = [
    "read_gpx",
    "write_gpx",
    "simplify_track",
    "Simplifier",
    "Track",
    "TrackPoint",
    "compression_ratio",
]
