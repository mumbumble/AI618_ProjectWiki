"""Speed benchmark for trackslim's Simplifier.

Times Simplifier.simplify on random-walk tracks of increasing size.
Each size is run REPEATS times and the median is kept. Results go to
benchmarks/results.csv as n_points,version,seconds. Rows recorded for
other versions are kept, so older runs stay in the file.

Usage:
    python benchmarks/bench_speed.py --version 0.4.0
"""

import argparse
import csv
import math
import random
import statistics
import time
from pathlib import Path

from trackslim.core import Simplifier, Track, TrackPoint

SIZES = [1000, 10000, 100000]
REPEATS = 5
SEED = 2026
RESULTS = Path(__file__).resolve().parent / "results.csv"
FIELDS = ["n_points", "version", "seconds"]


def make_track(n, rng):
    """Build a random-walk track of n points starting near Seoul."""
    lat, lon, ele = 37.5, 127.0, 50.0
    heading = rng.uniform(0, 2 * math.pi)
    points = []
    for _ in range(n):
        heading += rng.gauss(0, 0.3)
        step = rng.uniform(2e-5, 8e-5)
        lat += step * math.cos(heading)
        lon += step * math.sin(heading)
        ele += rng.gauss(0, 0.8)
        points.append(TrackPoint(lat=lat, lon=lon, ele=ele, time=None))
    return Track(points=points, name=f"walk_{n}")


def median_seconds(simplifier, track):
    """Run simplify REPEATS times and return the median wall time."""
    timings = []
    for _ in range(REPEATS):
        start = time.perf_counter()
        simplifier.simplify(track)
        timings.append(time.perf_counter() - start)
    return statistics.median(timings)


def load_rows(path):
    """Return existing result rows, or an empty list if the file is missing."""
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main():
    parser = argparse.ArgumentParser(description="Time trackslim simplification.")
    parser.add_argument("--version", required=True, help="version label for this run")
    args = parser.parse_args()

    simplifier = Simplifier(
        tolerance_m=5.0,
        turn_weight=2.0,
        elev_weight=0.5,
        min_turn_deg=35.0,
    )

    new_rows = []
    for n in SIZES:
        # Reseed for every size so each run sees the same tracks.
        track = make_track(n, random.Random(SEED))
        seconds = median_seconds(simplifier, track)
        new_rows.append({
            "n_points": str(n),
            "version": args.version,
            "seconds": f"{seconds:.3f}",
        })
        print(f"{n:>7} points  {args.version}  {seconds:.3f} s")

    kept = [row for row in load_rows(RESULTS) if row["version"] != args.version]
    rows = kept + new_rows

    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    with RESULTS.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {RESULTS}")


if __name__ == "__main__":
    main()
