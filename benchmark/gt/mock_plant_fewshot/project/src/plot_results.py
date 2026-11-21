"""Plot few-shot accuracy versus number of shots for the LeafProto paper.

Reads results/main_results.csv (columns: method, shots, accuracy, ci95)
and writes figures/accuracy_vs_shots.png.

Usage:
    python src/plot_results.py
    python src/plot_results.py --csv results/main_results.csv --out figures/accuracy_vs_shots.png
"""

import argparse
import os

import matplotlib

matplotlib.use("Agg")  # headless runs on the lab server
import matplotlib.pyplot as plt
import pandas as pd

METHOD_ORDER = ["Finetune", "ProtoClass", "FastAdapt", "LeafProto"]
STYLES = {
    "Finetune": {"color": "#999999", "marker": "s", "ls": "--"},
    "ProtoClass": {"color": "#1f77b4", "marker": "o", "ls": "-"},
    "FastAdapt": {"color": "#ff7f0e", "marker": "^", "ls": "-"},
    "LeafProto": {"color": "#d62728", "marker": "D", "ls": "-"},
}
SHOTS = [1, 2, 5, 10]


def load_results(csv_path):
    df = pd.read_csv(csv_path)
    required = {"method", "shots", "accuracy", "ci95"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{csv_path} is missing columns: {sorted(missing)}")
    df["shots"] = df["shots"].astype(int)
    return df


def plot_accuracy_vs_shots(df, out_path):
    fig, ax = plt.subplots(figsize=(6, 4.2))
    for method in METHOD_ORDER:
        sub = df[df["method"] == method].sort_values("shots")
        if sub.empty:
            print(f"warning: no rows for {method}, skipping")
            continue
        style = STYLES[method]
        ax.errorbar(
            sub["shots"],
            sub["accuracy"],
            yerr=sub["ci95"],
            label=method,
            color=style["color"],
            marker=style["marker"],
            linestyle=style["ls"],
            linewidth=1.8,
            markersize=6,
            capsize=3,
        )
    ax.set_xlabel("Number of shots (k)")
    ax.set_ylabel("Accuracy (%)")
    ax.set_xticks(SHOTS)
    ax.set_xlim(0.5, 10.5)
    ax.set_title("5-way episodes on leafdoc_fs")
    ax.grid(alpha=0.3)
    ax.legend(loc="lower right")
    fig.tight_layout()

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    fig.savefig(out_path, dpi=200)
    plt.close(fig)
    return out_path


def print_five_shot_gap(df):
    five = df[df["shots"] == 5].set_index("method")["accuracy"]
    if "LeafProto" in five and "FastAdapt" in five and "ProtoClass" in five:
        gap_fa = five["LeafProto"] - five["FastAdapt"]
        gap_pc = five["LeafProto"] - five["ProtoClass"]
        print(f"5-shot LeafProto {five['LeafProto']:.1f}%: "
              f"+{gap_fa:.1f} over FastAdapt, +{gap_pc:.1f} over ProtoClass")


def main():
    parser = argparse.ArgumentParser(description="Draw the accuracy-vs-shots figure.")
    parser.add_argument("--csv", default="results/main_results.csv")
    parser.add_argument("--out", default="figures/accuracy_vs_shots.png")
    args = parser.parse_args()

    df = load_results(args.csv)
    out = plot_accuracy_vs_shots(df, args.out)
    print(f"saved {out}")
    print_five_shot_gap(df)


if __name__ == "__main__":
    main()
