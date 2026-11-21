"""Speed benchmark for csvdelta.

Builds a random five-column table for each size, diffs it against a lightly
modified copy and records the median run time per size. Results go to
benchmarks/results.csv, replacing any earlier rows for the same version.
"""

import csv
import random
import statistics
import time
from pathlib import Path

import csvdelta
from csvdelta.core import Differ, Table

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results.csv"
SIZES = [10000, 100000, 1000000]
SEED = 7
RUNS = 5
HEADER = ["id", "name", "amount", "city", "flag"]
CITIES = ["Seoul", "Busan", "Daegu", "Incheon", "Gwangju", "Daejeon"]


def make_rows(n, rng):
    rows = []
    for i in range(1, n + 1):
        rows.append([
            str(i),
            f"name{rng.randrange(10**6)}",
            f"{rng.uniform(0, 1000):.2f}",
            rng.choice(CITIES),
            rng.choice(["0", "1"]),
        ])
    return rows


def make_variant(rows, rng):
    # About 1% of rows removed, about 5% with a changed amount.
    out = []
    for row in rows:
        roll = rng.random()
        if roll < 0.01:
            continue
        new_row = list(row)
        if roll < 0.06:
            new_row[2] = f"{float(row[2]) + 5:.2f}"
        out.append(new_row)
    return out


def time_diff(table_a, table_b):
    timings = []
    for _ in range(RUNS):
        start = time.perf_counter()
        Differ(key=["id"]).run(table_a, table_b)
        timings.append(time.perf_counter() - start)
    return statistics.median(timings)


def save_results(version, new_rows):
    kept = []
    if RESULTS.exists():
        with RESULTS.open(newline="") as fh:
            reader = csv.DictReader(fh)
            kept = [r for r in reader if r["version"] != version]
    with RESULTS.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["rows", "version", "seconds"])
        for r in kept:
            writer.writerow([r["rows"], r["version"], r["seconds"]])
        writer.writerows(new_rows)


def main():
    version = csvdelta.__version__
    results = []
    for n in SIZES:
        rng = random.Random(SEED)
        base = make_rows(n, rng)
        variant = make_variant(base, rng)
        table_a = Table(header=HEADER, rows=base)
        table_b = Table(header=HEADER, rows=variant)
        seconds = time_diff(table_a, table_b)
        print(f"{n:>9} rows  {seconds:.2f} s  (csvdelta {version})")
        results.append([n, version, f"{seconds:.2f}"])
    save_results(version, results)
    print(f"wrote {RESULTS}")


if __name__ == "__main__":
    main()
