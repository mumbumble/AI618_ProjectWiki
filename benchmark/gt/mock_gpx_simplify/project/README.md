# trackslim

trackslim is an open-source Python library that simplifies GPS tracks stored as GPX files. Unlike plain Douglas-Peucker, it keeps sharp turns and elevation changes, so a simplified hike or ride still looks right on the map and keeps its total ascent accurate.

- Turn-Aware Elevation-Weighted Douglas-Peucker (TAEW-DP) core algorithm
- Reads GPX 1.1, merges multiple `<trkseg>` segments into one track
- Writes GPX with `<ele>` and `<time>` preserved
- Command-line tool: `trackslim`
- No runtime dependencies beyond the standard library
- Python 3.9 or newer, MIT license

## Installation

Install the latest release from PyPI:

```bash
pip install trackslim
```

To check the installed version:

```bash
python -c "import trackslim; print(trackslim.__version__)"
```

To work from a source checkout (for development):

```bash
git clone https://github.com/trackslim/trackslim.git
cd trackslim
pip install -e .
```

## Quickstart (Python)

```python
from trackslim import read_gpx, write_gpx, simplify_track, compression_ratio

track = read_gpx("my_track.gpx")
slim = simplify_track(track, tolerance_m=5.0, turn_weight=2.0, elev_weight=0.5)

print(f"{len(track.points)} -> {len(slim.points)} points")
print(f"compression ratio: {compression_ratio(track, slim):.3f}")

write_gpx(slim, "my_track_slim.gpx")
```

For more control, use the `Simplifier` class directly:

```python
from trackslim import Simplifier, read_gpx

track = read_gpx("my_track.gpx")
simplifier = Simplifier(
    tolerance_m=5.0,     # maximum allowed horizontal deviation in metres
    turn_weight=2.0,     # extra cost for keeping turns
    elev_weight=0.5,     # weight of vertical deviation
    min_turn_deg=35.0,   # turns at or above this angle are always kept
)
slim = simplifier.simplify(track)
```

### Default settings

| Parameter     | Default | Meaning                                        |
|---------------|---------|------------------------------------------------|
| `tolerance_m` | 5.0     | Base tolerance in metres                       |
| `turn_weight` | 2.0     | Weight applied to turn angles                  |
| `elev_weight` | 0.5     | Weight applied to elevation deviation          |
| `min_turn_deg`| 35.0    | Points with a turn at least this sharp are kept |

Defaults can also be set in the TOML config file that ships with the project.

## Command-line usage

The `trackslim` console script is installed with the package. The CLI lives in `trackslim/cli.py`.

### Simplify a track

```bash
trackslim simplify IN.gpx OUT.gpx
```

Options:

- `--tolerance METERS`: tolerance in metres (default `5.0`)
- `--plugin NAME`: run a named plugin, for example `elevation_guard`

Example with a larger tolerance:

```bash
trackslim simplify my_track.gpx my_track_slim.gpx --tolerance 8.0
```

### Use the elevation guard plugin

For hiking tracks where total ascent matters, use the elevation guard plugin:

```bash
trackslim simplify my_track.gpx my_track_slim.gpx --plugin elevation_guard
```

The plugin subclasses `Simplifier` as `ElevationGuardSimplifier`. After simplification it re-inserts points wherever the cumulative climb differs from the original by more than `max_ele_error_m` (default 3.0 m).

### Show track statistics

```bash
trackslim stats my_track.gpx
```

This prints the number of points, track duration, and total ascent for the file.

## Results

Typical results at the default tolerance of 5.0 m:

- A 12,480-point track simplifies to 1,106 points (compression ratio 0.911), with a total ascent error of 1.8 m.

The demo notebook in `examples/demo.ipynb` walks through a sample ridge track: 1,842 points become 311 points at tolerance 8.0 (compression ratio about 0.831).

## Examples

The `examples/demo.ipynb` notebook shows how to load a track, compare tolerances, plot the original and simplified routes, and check elevation profiles. Open it with Jupyter:

```bash
pip install jupyter
jupyter notebook examples/demo.ipynb
```

## Development

Run the test suite with:

```bash
pip install -e .
python -m pytest
```

Issues and pull requests are welcome. Please include a small GPX file that reproduces any bug you report.

## License

trackslim is released under the MIT License.
