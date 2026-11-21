# Changelog

All notable changes to trackslim are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses [Semantic Versioning](https://semver.org/).

## [0.4.0] - 2026-10-30

### Added
- `ElevationGuard` plugin. It subclasses `Simplifier` and adds a `max_ele_error_m` setting (default 3.0). After simplification it re-inserts points wherever the cumulative climb drifts from the original by more than that value, so total ascent stays accurate on hiking tracks.
- `stats` command in the CLI: `trackslim stats IN.gpx` prints point counts, total ascent and descent, and track length.

### Changed
- The simplification loop now uses an iterative stack instead of recursion, so very long tracks no longer hit the Python recursion limit.
- Cumulative projection values are precomputed once per track. This is pure stdlib code, so there is still no numpy dependency.
- On 100,000 points, `simplify` is about 1.77x faster than in 0.3.1 (3.51 s down to 1.99 s, median of 5 runs).

## [0.3.1] - 2026-09-14

### Fixed
- `read_gpx` dropped the final trackpoint of every `<trkseg>` after the first when a GPX file contained more than one segment. A file with two segments of three points each returned 5 points instead of 6. The reader now keeps the last point of every segment. Reported in #37. This affected 0.3.0 only for multi-segment files. A regression test covers the case.

## [0.3.0] - 2026-08-25

### Added
- `turn_weight` parameter on `Simplifier` and `simplify_track`. Turns add a cost term to the weighted error, so sharp direction changes survive simplification.
- Forced keep for points whose turn angle is at or above `min_turn_deg` (default 35.0 degrees).
- TOML configuration support. The CLI reads defaults from a `[simplify]`, `[plugin]`, and `[output]` section, using `tomllib` with a `tomli` fallback on Python 3.9 and 3.10.

### Changed
- The weighted error is now the horizontal perpendicular distance plus an elevation term and a turn term, instead of distance alone.

## [0.2.0] - 2026-06-20

### Added
- Command-line interface with the `trackslim simplify IN.gpx OUT.gpx` command.
- `--tolerance` option to set the distance tolerance in meters from the command line (default 5.0).
- `--plugin` option to select a plugin by name.
- `compression_ratio` helper, which returns `1 - len(simplified) / len(original)`.

### Changed
- `write_gpx` now writes `<ele>` and `<time>` elements when they are present on the points.
