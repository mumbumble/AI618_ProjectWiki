"""Analysis of VRType task logs (time and errors).

Reads data/task_logs.csv (participant, condition, task_id, seconds, errors).
For each participant, the four task values per condition are averaged.
Ray-casting keyboard ("ray") and hand-tracking swipe keyboard ("swipe") are
compared with a two-sided Wilcoxon signed-rank test on the paired
per-participant means. Alpha = .05. No correction is applied between the
time test and the error test.

Usage:
    python analysis/analyze_logs.py --input data/task_logs.csv
"""

import argparse
import csv
import math
from collections import defaultdict
from statistics import mean, stdev

from scipy.stats import wilcoxon

LOG_PATH = "data/task_logs.csv"
CONDITIONS = ("ray", "swipe")
TASKS = ("T1", "T2", "T3", "T4")
ALPHA = 0.05


def load_logs(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append({
                "participant": row["participant"].strip(),
                "condition": row["condition"].strip(),
                "task_id": row["task_id"].strip(),
                "seconds": float(row["seconds"]),
                "errors": float(row["errors"]),
            })
    return rows


def per_participant_means(rows, measure):
    """Return {condition: {participant: mean of measure over tasks}}."""
    buckets = defaultdict(lambda: defaultdict(list))
    for r in rows:
        buckets[r["condition"]][r["participant"]].append(r[measure])
    return {
        cond: {p: mean(vals) for p, vals in parts.items()}
        for cond, parts in buckets.items()
    }


def per_task_means(rows, measure):
    buckets = defaultdict(list)
    for r in rows:
        buckets[(r["condition"], r["task_id"])].append(r[measure])
    return {key: mean(vals) for key, vals in buckets.items()}


def paired_wilcoxon(means):
    shared = sorted(set(means["ray"]) & set(means["swipe"]))
    ray = [means["ray"][p] for p in shared]
    swipe = [means["swipe"][p] for p in shared]
    stat, p_value = wilcoxon(ray, swipe, alternative="two-sided")
    # Effect size r = |Z| / sqrt(N), Z from the normal approximation.
    n = sum(1 for a, b in zip(ray, swipe) if a != b)
    mu = n * (n + 1) / 4
    sigma = math.sqrt(n * (n + 1) * (2 * n + 1) / 24)
    z = (stat - mu) / sigma
    r = abs(z) / math.sqrt(n)
    return len(shared), stat, p_value, r


def report_measure(rows, measure, unit, label):
    means = per_participant_means(rows, measure)
    print(f"== {label} ({unit}) ==")
    for cond in CONDITIONS:
        values = list(means[cond].values())
        print(f"  {cond:<6} mean {mean(values):6.2f}  SD {stdev(values):5.2f}  n={len(values)}")
    change = (mean(means["swipe"].values()) - mean(means["ray"].values())) \
        / mean(means["ray"].values()) * 100
    print(f"  swipe vs ray: {change:+.1f}%")

    n, stat, p_value, r = paired_wilcoxon(means)
    print(f"  Wilcoxon signed-rank (two-sided, n={n}): W = {stat:g}, "
          f"p = {p_value:.3f}, r = {r:.2f}")
    print(f"  significant at alpha {ALPHA}: {'yes' if p_value < ALPHA else 'no'}")
    print()


def report_per_task(rows):
    print("== Per-task means ==")
    print(f"  {'task':<6}{'seconds ray':>13}{'seconds swipe':>15}"
          f"{'errors ray':>12}{'errors swipe':>14}")
    sec = per_task_means(rows, "seconds")
    err = per_task_means(rows, "errors")
    for task in TASKS:
        print(f"  {task:<6}"
              f"{sec[('ray', task)]:>13.1f}{sec[('swipe', task)]:>15.1f}"
              f"{err[('ray', task)]:>12.1f}{err[('swipe', task)]:>14.1f}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Analyze VRType task logs.")
    parser.add_argument("--input", default=LOG_PATH, help="path to task_logs.csv")
    args = parser.parse_args()

    rows = load_logs(args.input)
    print(f"Loaded {len(rows)} task rows from {args.input}")
    print()

    report_measure(rows, "seconds", "seconds per task", "Time")
    report_measure(rows, "errors", "errors per task", "Errors")
    report_per_task(rows)


if __name__ == "__main__":
    main()
