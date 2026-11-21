"""Plot grasp success rate vs. randomization range for the main GraspDR results.

Reads results/main_results.csv and writes the Figure 2 PNG used in the paper.
Run from the repository root:

    python src/plot_results.py
"""
import csv
import os
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULTS_CSV = "results/main_results.csv"
FIG_PATH = "figures/success_rate_vs_randomization_range.png"

METHOD_ORDER = ["GraspDR", "ADR-Grasp", "SimBridge", "Uniform DR", "No DR"]
STYLE = {
    "GraspDR": dict(color="#d62728", marker="o", linewidth=2.5, zorder=5),
    "ADR-Grasp": dict(color="#1f77b4", marker="s"),
    "SimBridge": dict(color="#2ca02c", marker="^"),
    "Uniform DR": dict(color="#9467bd", marker="D", linestyle="--"),
    "No DR": dict(color="#7f7f7f", marker="x", linestyle=":"),
}
RANGE_TICKS = [0.5, 1.0, 1.5, 2.0, 2.5]


def load_results(path):
    """Return {method: [(range, success, ci95), ...]} sorted by range."""
    table = defaultdict(list)
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            method = row["method"].strip()
            table[method].append((
                float(row["randomization_range"]),
                float(row["success_rate"]),
                float(row["ci95_half_width"]),
            ))
    for method in table:
        table[method].sort(key=lambda t: t[0])
    return table


def plot(table, out_path):
    fig, ax = plt.subplots(figsize=(6.4, 4.4))

    for method in METHOD_ORDER:
        if method not in table:
            print(f"warning: no rows for {method}, skipping")
            continue
        rows = table[method]
        x = [r[0] for r in rows]
        y = [r[1] for r in rows]
        ci = [r[2] for r in rows]
        ax.errorbar(x, y, yerr=ci, capsize=3, label=method, **STYLE[method])

    ax.axvline(1.5, color="black", linestyle=":", linewidth=0.8, alpha=0.5)
    ax.set_xlabel("Randomization range scale s")
    ax.set_ylabel("Grasp success rate (%)")
    ax.set_xticks(RANGE_TICKS)
    ax.set_xlim(0.4, 2.6)
    ax.set_ylim(20, 100)
    ax.grid(alpha=0.3)
    ax.legend(loc="lower left", frameon=False)
    fig.tight_layout()

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    print(f"saved {out_path}")


def main():
    table = load_results(RESULTS_CSV)
    if not table:
        raise SystemExit(f"no rows found in {RESULTS_CSV}")
    plot(table, FIG_PATH)


if __name__ == "__main__":
    main()
