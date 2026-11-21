"""Survey analysis for the ReviewLens explanation-style study.

Reads the post-task questionnaire responses (one row per participant and
condition), computes the trust composite (mean of Q1-Q3), prints item-level
summaries, and saves the main trust figure.

Usage:
    python analysis/analyze_survey.py
"""
from pathlib import Path
import csv
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
SURVEY_PATH = ROOT / "data" / "survey_responses.csv"
FIG_PATH = ROOT / "results" / "figures" / "trust_composite_by_condition.png"

CONDITIONS = ["terse", "rationale", "trace"]
ITEMS = [f"Q{i}" for i in range(1, 9)]
TRUST_ITEMS = ["Q1", "Q2", "Q3"]

# Two-sided 95% t critical values, keyed by degrees of freedom (n - 1)
T_CRITICAL = {9: 2.262, 19: 2.093}


def load_rows(path):
    """Read survey rows, validate them, and add the trust composite."""
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        if row["condition"] not in CONDITIONS:
            raise ValueError(f"Unknown condition code: {row['condition']}")
        for item in ITEMS:
            value = int(row[item])
            if not 1 <= value <= 7:
                raise ValueError(f"{row['participant']} {item} out of range: {value}")
            row[item] = value
        row["trust"] = statistics.mean(row[i] for i in TRUST_ITEMS)
    return rows


def values_for(rows, condition, key):
    return [r[key] for r in rows if r["condition"] == condition]


def print_item_table(rows):
    print("Item means (1-7) by condition")
    print(f"{'item':<6}" + "".join(f"{c:>11}" for c in CONDITIONS))
    for item in ITEMS:
        cells = [
            f"{statistics.mean(values_for(rows, c, item)):>11.1f}"
            for c in CONDITIONS
        ]
        print(f"{item:<6}" + "".join(cells))


def trust_summary(rows):
    """Return per-condition means and 95% CI half-widths for the composite."""
    means, half_widths = [], []
    print("\nTrust composite (mean of Q1-Q3)")
    for cond in CONDITIONS:
        vals = values_for(rows, cond, "trust")
        m = statistics.mean(vals)
        sd = statistics.stdev(vals)
        t = T_CRITICAL[len(vals) - 1]
        ci = t * sd / len(vals) ** 0.5
        means.append(m)
        half_widths.append(ci)
        print(f"  {cond:<10} M={m:.2f}  SD={sd:.2f}  95% CI +/- {ci:.2f}")
    return means, half_widths


def plot_trust(means, half_widths, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(5, 4), dpi=150)
    colors = ["#9e9e9e", "#5b8db8", "#2e6f40"]
    bars = ax.bar(
        CONDITIONS, means, yerr=half_widths, capsize=6,
        color=colors, edgecolor="black", linewidth=0.7,
    )
    for bar, m, h in zip(bars, means, half_widths):
        ax.text(
            bar.get_x() + bar.get_width() / 2, m + h + 0.1,
            f"{m:.2f}", ha="center", va="bottom", fontsize=9,
        )
    ax.set_ylim(1, 7)
    ax.set_xlabel("Explanation condition")
    ax.set_ylabel("Trust composite (mean of Q1-Q3, 1-7)")
    ax.set_title("Trust by explanation style (N=10, within-subjects)", fontsize=10)
    ax.grid(axis="y", linestyle=":", alpha=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main():
    rows = load_rows(SURVEY_PATH)
    counts = {c: len(values_for(rows, c, "trust")) for c in CONDITIONS}
    print(f"Loaded {len(rows)} survey rows: {counts}\n")

    print_item_table(rows)
    means, half_widths = trust_summary(rows)
    plot_trust(means, half_widths, FIG_PATH)
    print(f"\nFigure saved to {FIG_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
