# trackslim Design Document

## Overview

trackslim is an open-source Python library that simplifies GPS tracks stored as GPX files. Plain Douglas-Peucker removes points using horizontal distance alone, which can flatten sharp turns and erase elevation peaks. trackslim keeps both. Its core algorithm is Turn-Aware Elevation-Weighted Douglas-Peucker (TAEW-DP), implemented in trackslim/core.py.

The package is named `trackslim` on PyPI, is MIT licensed, and supports Python 3.9 and newer.

## Architecture

The library has three layers, with a command-line interface on top.

1. **IO layer**: reads and writes GPX files.
2. **Core layer**: the data types and the simplifier in trackslim/core.py. It does not touch files.
3. **Plugins**: optional subclasses of core classes that change how simplification works.
4. **CLI**: a thin wrapper that connects the layers for shell use.

Dependencies point inward. The CLI and plugins depend on the core, and the IO layer depends on the core types. The core never imports from the IO layer or the CLI.

## Modules

### File reading and writing

The reader/writer module of the IO layer exposes these functions:

- `read_gpx(path) -> Track` parses the file and returns one Track.
- `write_gpx(track, path)` writes a Track as GPX 1.1, using `<trk><trkseg><trkpt lat lon>` with `<ele>` and `<time>` children.
- `parse_time(text)` parses ISO-8601 timestamps and accepts a trailing `Z`.
- `_read_trkpts(root)` is a private helper that collects the track points from the parsed XML tree.

The reader is responsible for the following:

- Parsing the XML with the standard library `xml.etree.ElementTree` and the GPX 1.1 namespace.
- Merging all `<trkseg>` segments into one Track in document order. Every point in every segment is kept, including the last point of each segment.
- Parsing ISO-8601 timestamps.
- Tolerating a missing `<ele>`. The point gets `ele=0.0` and a warning is logged.

### Core

Two immutable dataclasses hold the data:

- `TrackPoint(lat, lon, ele, time)`
- `Track(points, name)`

Three helper functions do the geometry:

- `perpendicular_distance_m(p, a, b)` returns the horizontal distance in metres from point p to the segment a-b.
- `turn_angle_deg(a, b, c)` returns the change of heading at b, in degrees.
- `weighted_error(p, a, b)` returns the cost used to decide whether p can be dropped.

`Simplifier(tolerance_m, turn_weight, elev_weight, min_turn_deg)` has one public method, `simplify(track) -> Track`. The weighted error is:

```
error = horizontal perpendicular distance
      + elev_weight * vertical deviation from interpolated elevation
      + turn_weight * (turn angle in degrees / 180) * tolerance_m
```

Any point whose turn angle is at least `min_turn_deg` is always kept, whatever its error. Default values are `tolerance_m=5.0`, `turn_weight=2.0`, `elev_weight=0.5`, and `min_turn_deg=35.0`.

Two convenience functions sit on top of the simplifier:

- `simplify_track(track, tolerance_m=5.0, turn_weight=2.0, elev_weight=0.5) -> Track` wraps `Simplifier`.
- `compression_ratio(original, simplified) -> float` returns `1 - len(simplified) / len(original)`.

### Plugins

A plugin is a module in the plugins package that defines a subclass of `Simplifier`. Each plugin is listed in the `PLUGINS` dict of the plugins package under its name. A user selects a plugin in one of two ways: by passing `--plugin` with its registry name on the command line, or by importing the class directly in Python code.

The bundled plugin is `ElevationGuardSimplifier(Simplifier)`. It adds a `max_ele_error_m=3.0` setting. After the base simplification, it compares the cumulative climb of the original and simplified tracks. Wherever the two differ by more than `max_ele_error_m`, it re-inserts points. Its purpose is to keep total ascent accurate for hiking tracks.

### CLI

The `trackslim` console script provides two commands:

- `trackslim simplify IN.gpx OUT.gpx` with options `--tolerance`, default 5.0, and `--plugin`.
- `trackslim stats IN.gpx` prints summary figures for a track.

Settings are read from the default TOML config file with `tomllib`. On Python 3.9 and 3.10 the `tomli` package is used instead. The file has three sections: `[simplify]` with the four simplifier parameters, `[plugin]` with a `name` key, and `[output]` with `precision=6` and `keep_time=true`.

## Data flow

1. `read_gpx` parses the GPX file and returns a Track.
2. `Simplifier.simplify` (or a plugin subclass) reduces the Track.
3. `write_gpx` writes the simplified Track to a new GPX file.

## Decisions

- **Iterative stack instead of recursion.** Douglas-Peucker is naturally recursive, but long tracks would hit Python's recursion limit. An explicit stack avoids that.
- **Standard library XML only.** The package has no runtime dependencies beyond the standard library, which keeps installation simple.
- **Elevation as a cost term.** Elevation error is added to the same weighted error as horizontal distance rather than acting as a separate filter. This keeps the algorithm a single pass over one error measure.
- **Turns as forced keeps plus a weighted term.** Sharp turns are never dropped, and gentler turns add a smaller cost.
- **Immutable dataclasses.** Tracks and points cannot change after creation, so they can be shared safely between simplifier runs and plugins.
- **Precomputed cumulative projection.** Coordinates are projected once per track, so each error check is cheap.

## Limitations

- Distances are computed in 2D. There is no 3D geodesic distance; horizontal distance uses an equirectangular projection, which is accurate for short tracks but drifts over large extents.
- Elevation deviation is measured vertically against linear interpolation between kept points.
- Simplification runs on a single thread.
- Points without `<ele>` are given `0.0`, which can distort the elevation error for those points.

## Planned changes

The project roadmap plans the following changes to this architecture.

- **0.5.0 (2026-12):** CSV export is added to the IO layer. A KML reader becomes a second reader beside the GPX reader. Segments are simplified in parallel.
- **1.0.0 (2027-03):** The public API is declared stable. Geodesic 3D distance replaces the equirectangular projection in the core. The plugin registry is discovered through entry points instead of a fixed dict.
