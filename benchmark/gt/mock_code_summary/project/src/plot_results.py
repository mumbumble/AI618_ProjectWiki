"""Draw Figure 2: BLEU-4 on intra_repo as a function of the number of retrieved functions k.

Usage (from the repo root):
    python src/plot_results.py
"""
import csv
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS_CSV = os.path.join(ROOT, "results", "main_results.csv")
FIG_DIR = os.path.join(ROOT, "figures")
FIG_PATH = os.path.join(FIG_DIR, "bleu4_vs_num_retrieved.png")

SETTING = "intra_repo"
K_VALUES = [0, 1, 2, 4, 8, 16]
K_MAIN = 4  # k used for the main table and the reported CIs

# BLEU-4 sweep over k. k=0 is the plain Transformer, shared by all curves.
SWEEP = {
    "RepoSum": [20.4, 24.3, 25.4, 26.1, 26.0, 25.6],
    "CodeSibling": [20.4, 22.5, 23.4, 23.7, 23.2, 22.6],
    "RetroSum": [20.4, 21.8, 22.4, 22.6, 22.3, 21.9],
}
STYLE = {
    "RepoSum": dict(marker="o", linestyle="-"),
    "CodeSibling": dict(marker="s", linestyle="--"),
    "RetroSum": dict(marker="^", linestyle=":"),
}


def load_results(path):
    results = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            results[(row["method"], row["setting"])] = {
                "bleu4": float(row["bleu4"]),
                "ci_low": float(row["ci_low"]),
                "ci_high": float(row["ci_high"]),
            }
    return results


def check_consistency(results):
    """Make sure the hard-coded sweep agrees with the main results table."""
    transformer = results[("Transformer", SETTING)]["bleu4"]
    k_idx = K_VALUES.index(K_MAIN)
    for method, curve in SWEEP.items():
        if abs(curve[0] - transformer) > 1e-6:
            raise ValueError(f"k=0 for {method} does not match Transformer")
        main = results[(method, SETTING)]["bleu4"]
        if abs(curve[k_idx] - main) > 1e-6:
            raise ValueError(f"k={K_MAIN} for {method} does not match main table")


def main():
    results = load_results(RESULTS_CSV)
    check_consistency(results)

    # Evenly spaced positions, so the powers of two read as equal steps.
    x = list(range(len(K_VALUES)))
    fig, ax = plt.subplots(figsize=(6, 4))
    for method, curve in SWEEP.items():
        ax.plot(x, curve, label=method, linewidth=1.8, markersize=6, **STYLE[method])

    # 95% bootstrap confidence intervals at the main setting k=4.
    k_idx = K_VALUES.index(K_MAIN)
    for method in SWEEP:
        r = results[(method, SETTING)]
        yerr = [[r["bleu4"] - r["ci_low"]], [r["ci_high"] - r["bleu4"]]]
        ax.errorbar(x[k_idx], r["bleu4"], yerr=yerr, fmt="none",
                    ecolor="gray", capsize=3)

    ax.set_xticks(x)
    ax.set_xticklabels([str(k) for k in K_VALUES])
    ax.set_xlabel("Number of retrieved functions k")
    ax.set_ylabel("BLEU-4 (intra_repo)")
    ax.grid(alpha=0.3)
    ax.legend(frameon=False)
    fig.tight_layout()

    os.makedirs(FIG_DIR, exist_ok=True)
    fig.savefig(FIG_PATH, dpi=300)
    plt.close(fig)
    print(f"saved {FIG_PATH}")


if __name__ == "__main__":
    main()
