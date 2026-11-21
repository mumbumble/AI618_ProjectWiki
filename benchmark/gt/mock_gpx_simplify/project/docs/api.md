# trackslim API Reference

This page documents every public name exported by the `trackslim` package. Version 0.4.0.

`trackslim` has no runtime dependencies beyond the standard library. It reads and writes GPX 1.1 files and simplifies GPS tracks with the Turn-Aware Elevation-Weighted Douglas-Peucker (TAEW-DP) algorithm, which keeps turns and elevation changes that plain Douglas-Peucker would drop.

## Data types

### `TrackPoint(lat, lon, ele, time)`

A single immutable point on a track.

| Field  | Type            | Description                                  |
|--------|-----------------|----------------------------------------------|
| `lat`  | `float`         | Latitude in decimal degrees.                 |
| `lon`  | `float`         | Longitude in decimal degrees.                |
| `ele`  | `float`         | Elevation in metres. `0.0` when `<ele>` is missing in the file. |
| `time` | `datetime` or `None` | Timestamp parsed from ISO-8601. |

### `Track(points, name)`

An immutable ordered sequence of `TrackPoint` objects.

- `points`: the track points, in order.
- `name`: the track name taken from the GPX file, or a user-supplied string.

## Reading and writing

### `read_gpx(path) -> Track`

Parses a GPX file and returns a single `Track`.

- Handles the GPX 1.1 namespace.
- Merges every `<trkseg>` in the file into one `Track`, in document order.
- Parses ISO-8601 timestamps, including a trailing `Z`.
- A point without `<ele>` gets `ele=0.0` and a warning is logged.
- Multi-segment files return every point. Earlier versions dropped the last point of each later segment; this was fixed in 0.3.1 (issue #37).

### `write_gpx(track, path)`

Writes a `Track` to a GPX file. The output contains one `<trk>` with one `<trkseg>`, and each point is written as `<trkpt lat lon>` with `<ele>` and `<time>` children. Coordinates and elevation use the precision and time settings from the configuration file.

## Simplification

### `Simplifier(tolerance_m=5.0, turn_weight=2.0, elev_weight=0.5, min_turn_deg=35.0)`

The core simplifier. Create one instance and reuse it for several tracks.

| Parameter      | Default | Meaning |
|----------------|---------|---------|
| `tolerance_m`  | `5.0`   | Maximum allowed weighted error, in metres, before a point is kept. |
| `turn_weight`  | `2.0`   | Multiplier for the turn term in the error. |
| `elev_weight`  | `0.5`   | Multiplier for the vertical deviation term. |
| `min_turn_deg` | `35.0`  | Points with a turn angle at or above this value are always kept. |

#### `Simplifier.simplify(track) -> Track`

Returns a new `Track` with a subset of the input points, in the original order. The first and last points are always kept.

The error for a candidate point `p` between anchors `a` and `b` is:

```
error = horizontal perpendicular distance(p, a, b)
      + elev_weight * vertical deviation from the interpolated elevation
      + turn_weight * (turn angle in degrees / 180) * tolerance_m
```

A point is dropped when its error is within `tolerance_m`. Any point whose turn angle is at least `min_turn_deg` is kept regardless of error.

The algorithm uses an explicit stack instead of recursion, so very long tracks do not hit the Python recursion limit.

### `simplify_track(track, tolerance_m=5.0, turn_weight=2.0, elev_weight=0.5) -> Track`

Convenience wrapper that builds a `Simplifier` with the given values and calls `simplify` on the track. It uses the default `min_turn_deg` of `35.0`. Use `Simplifier` directly if you need to change that value.

## Metrics

### `compression_ratio(original, simplified) -> float`

Returns `1 - len(simplified) / len(original)`, where both arguments are `Track` objects. The result is `0.0` when nothing was removed and approaches `1.0` as more points are removed.

Example: a 10-point track simplified to 4 points gives `0.6`.

Example from the demo notebook: a 1,842-point ridge track simplified with `tolerance_m=8.0` to 311 points gives a ratio of about `0.831`.

## Usage

```python
track = read_gpx("morning_ridge.gpx")
small = simplify_track(track, tolerance_m=8.0)
print(compression_ratio(track, small))
write_gpx(small, "morning_ridge_small.gpx")
```

The command-line tool `trackslim simplify` runs the same steps and accepts `--tolerance` and `--plugin` options. See the design notes for how the reader, core simplifier, and plugins fit together.

## Version

The installed version is available as `trackslim.__version__`, currently `"0.4.0"`.
