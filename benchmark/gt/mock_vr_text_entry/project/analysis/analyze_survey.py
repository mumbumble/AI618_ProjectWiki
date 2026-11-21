"""Summarise post-condition Likert ratings and save the item-level figure.

Usage (from the project root):
    python analysis/analyze_survey.py

Reads data/survey_responses.csv (one row per participant and condition,
7-point Likert items Q1-Q8, 1 = strongly disagree, 7 = strongly agree)
and writes results/figures/likert_means_by_item.png.
"""

import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SURVEY_PATH = "data/survey_responses.csv"
FIG_PATH = "results/figures/likert_means_by_item.png"
ITEMS = [f"Q{i}" for i in range(1, 9)]
CONDITIONS = [("ray", "Ray", "#8c8c8c"), ("swipe", "Swipe", "#1f77b4")]
T_CRIT_95 = 2.131  # two-sided t, df = 15 (N = 16 participants)


def load_ratings(path):
    ratings = {cond: {q: [] for q in ITEMS} for cond, _, _ in CONDITIONS}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cond = row["condition"].strip()
            if cond not in ratings:
                continue
            for q in ITEMS:
                value = float(row[q])
                if not 1 <= value <= 7:
                    raise ValueError(f"{row['participant']} {q}: {value} is outside 1-7")
                ratings[cond][q].append(value)
    return ratings


def mean_ci(values):
    arr = np.asarray(values, dtype=float)
    se = arr.std(ddof=1) / np.sqrt(len(arr))
    return arr.mean(), T_CRIT_95 * se


def main():
    ratings = load_ratings(SURVEY_PATH)

    stats = {}
    print(f"{'item':<6}{'condition':<10}{'n':>4}{'mean':>8}{'95% CI':>10}")
    for cond, label, _ in CONDITIONS:
        stats[cond] = {q: mean_ci(ratings[cond][q]) for q in ITEMS}
        for q in ITEMS:
            m, ci = stats[cond][q]
            n = len(ratings[cond][q])
            print(f"{q:<6}{label:<10}{n:>4}{m:>8.2f}{ci:>10.2f}")

    x = np.arange(len(ITEMS))
    width = 0.38
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for i, (cond, label, color) in enumerate(CONDITIONS):
        means = [stats[cond][q][0] for q in ITEMS]
        errs = [stats[cond][q][1] for q in ITEMS]
        offset = (i - 0.5) * width
        ax.bar(x + offset, means, width, yerr=errs, capsize=3,
               label=label, color=color)

    ax.set_xticks(x)
    ax.set_xticklabels(ITEMS)
    ax.set_ylim(0, 7)
    ax.set_yticks(range(1, 8))
    ax.set_ylabel("Mean rating (1-7)")
    ax.set_title("Post-condition ratings by item")
    ax.legend(loc="upper right")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()

    os.makedirs(os.path.dirname(FIG_PATH), exist_ok=True)
    fig.savefig(FIG_PATH, dpi=200)
    plt.close(fig)
    print(f"Saved figure to {FIG_PATH}")


if __name__ == "__main__":
    main()
