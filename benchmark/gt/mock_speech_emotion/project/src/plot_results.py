"""Draw the UA-vs-SNR robustness figure used in the paper.

Reads results/main_results.csv, keeps the snr rows (snr0, snr5, snr10, snr20)
and saves figures/unweighted_accuracy_vs_snr_db.png.

Usage (from the project root):
    python src/plot_results.py
"""
import csv
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULTS_CSV = os.path.join("results", "main_results.csv")
OUT_PNG = os.path.join("figures", "unweighted_accuracy_vs_snr_db.png")

SNR_SETTINGS = {"snr0": 0, "snr5": 5, "snr10": 10, "snr20": 20}

METHOD_LABELS = {
    "egemaps_svm": "eGeMAPS + SVM",
    "emoformer2021": "EmoFormer (2021)",
    "crossling_ser2023": "CrossLingSER (2023)",
    "prosody_ser": "ProsodySER (ours)",
}

STYLES = {
    "egemaps_svm": dict(color="0.55", linestyle=":", marker="s"),
    "emoformer2021": dict(color="tab:green", linestyle="--", marker="^"),
    "crossling_ser2023": dict(color="tab:blue", linestyle="-.", marker="o"),
    "prosody_ser": dict(color="tab:red", linestyle="-", marker="D", linewidth=2.2),
}


def load_snr_rows(path):
    """Return {method: [(snr_db, ua, ci_low, ci_high), ...]} sorted by SNR."""
    curves = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if row["setting"] not in SNR_SETTINGS:
                continue
            snr = SNR_SETTINGS[row["setting"]]
            point = (snr, float(row["ua"]), float(row["ci_low"]), float(row["ci_high"]))
            curves.setdefault(row["method"], []).append(point)
    for method in curves:
        curves[method].sort()
    return curves


def print_gaps(curves):
    """Report the ProsodySER lead over the strongest baseline at each SNR."""
    ours = {p[0]: p[1] for p in curves["prosody_ser"]}
    base = {p[0]: p[1] for p in curves["crossling_ser2023"]}
    for snr in sorted(ours):
        print(f"SNR {snr:>2} dB: ProsodySER - CrossLingSER = {ours[snr] - base[snr]:+.1f} UA")


def main():
    curves = load_snr_rows(RESULTS_CSV)
    missing = [m for m in METHOD_LABELS if m not in curves]
    if missing:
        raise SystemExit(f"No SNR rows found for: {', '.join(missing)}")

    fig, ax = plt.subplots(figsize=(5.5, 4.0))
    for method, label in METHOD_LABELS.items():
        pts = curves[method]
        snr = [p[0] for p in pts]
        ua = [p[1] for p in pts]
        yerr = [[p[1] - p[2] for p in pts], [p[3] - p[1] for p in pts]]
        ax.errorbar(snr, ua, yerr=yerr, label=label, capsize=3,
                    markersize=5, **STYLES[method])

    ax.set_xlabel("SNR (dB)")
    ax.set_ylabel("Unweighted accuracy (%)")
    ax.set_xticks([0, 5, 10, 20])
    ax.set_xlim(-1, 21)
    ax.set_ylim(30, 80)
    ax.grid(alpha=0.3)
    ax.legend(loc="lower right", fontsize=8, frameon=False)
    ax.set_title("Babble-noise robustness on the mixed test set", fontsize=10)
    fig.tight_layout()

    os.makedirs(os.path.dirname(OUT_PNG), exist_ok=True)
    fig.savefig(OUT_PNG, dpi=300)
    plt.close(fig)

    print_gaps(curves)
    print(f"Saved {OUT_PNG}")


if __name__ == "__main__":
    main()
