"""Evaluate a trained ProsodySER checkpoint and write the main results CSV.

Primary metric is unweighted accuracy (UA): the mean per-class recall,
reported in percent. Confidence intervals come from a 1000-resample
bootstrap over the test utterances.
"""
import argparse
import csv
import os

import numpy as np
import torch
import yaml
from torch.utils.data import DataLoader

from prosody_ser_model import ProsodySER
from data import KoEnEmoDataset, make_loaders

SNR_LEVELS = [20, 10, 5, 0]
N_CLASSES = 6
N_BOOT = 1000
CSV_HEADER = ["method", "setting", "ua", "ci_low", "ci_high"]


def load_config(path):
    with open(path) as f:
        cfg = yaml.safe_load(f)
    parent = cfg.pop("inherits", None)
    if parent:
        base = load_config(os.path.join(os.path.dirname(path), parent))
        base.update(cfg)
        return base
    return cfg


def unweighted_accuracy(y_true, y_pred, n_classes=N_CLASSES):
    recalls = []
    for c in range(n_classes):
        mask = y_true == c
        if mask.any():
            recalls.append((y_pred[mask] == c).mean())
    return 100.0 * float(np.mean(recalls))


def bootstrap_ci(y_true, y_pred, n_boot=N_BOOT, seed=1234):
    rng = np.random.default_rng(seed)
    n = len(y_true)
    stats = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, n, n)
        stats[i] = unweighted_accuracy(y_true[idx], y_pred[idx])
    low, high = np.percentile(stats, [2.5, 97.5])
    return float(low), float(high)


@torch.no_grad()
def predict(model, loader, device):
    model.eval()
    labels, preds, langs = [], [], []
    for batch in loader:
        out = model(batch["features"].to(device), batch["mask"].to(device))
        preds.append(out["emotion_logits"].argmax(dim=-1).cpu().numpy())
        labels.append(batch["emotion"].numpy())
        langs.extend(batch["lang"])
    return np.concatenate(labels), np.concatenate(preds), np.array(langs)


def snr_loader(cfg, snr_db):
    ds = KoEnEmoDataset(cfg, split="test", snr_db=snr_db)
    return DataLoader(ds, batch_size=cfg["batch_size"], shuffle=False)


def write_results(path, method, rows):
    kept = []
    if os.path.exists(path):
        with open(path, newline="") as f:
            kept = [r for r in csv.DictReader(f) if r["method"] != method]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)
        for r in kept:
            writer.writerow([r[k] for k in CSV_HEADER])
        for setting, ua, lo, hi in rows:
            writer.writerow([method, setting, f"{ua:.1f}", f"{lo:.1f}", f"{hi:.1f}"])


def main():
    ap = argparse.ArgumentParser(description="Evaluate ProsodySER and write UA results.")
    ap.add_argument("--ckpt", required=True, help="best checkpoint file from checkpoints/")
    ap.add_argument("--config", required=True, help="experiment YAML config")
    ap.add_argument("--method", default="prosody_ser")
    ap.add_argument("--out", default="results/main_results.csv")
    args = ap.parse_args()

    cfg = load_config(args.config)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    model = ProsodySER(cfg).to(device)
    state = torch.load(args.ckpt, map_location=device)
    model.load_state_dict(state["model"] if "model" in state else state)

    loaders = make_loaders(cfg)
    labels, preds, langs = predict(model, loaders["test"], device)

    subsets = {
        "ko": langs == "ko",
        "en": langs == "en",
        "all": np.ones(len(labels), dtype=bool),
    }
    cases = [(name, labels[m], preds[m]) for name, m in subsets.items()]
    for snr in SNR_LEVELS:
        y, p, _ = predict(model, snr_loader(cfg, snr), device)
        cases.append((f"snr{snr}", y, p))

    table = []
    for setting, y, p in cases:
        ua = unweighted_accuracy(y, p)
        lo, hi = bootstrap_ci(y, p)
        table.append((setting, ua, lo, hi))
        print(f"{args.method:>14} {setting:>6}  UA {ua:5.1f}  [{lo:.1f}, {hi:.1f}]")

    write_results(args.out, args.method, table)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
