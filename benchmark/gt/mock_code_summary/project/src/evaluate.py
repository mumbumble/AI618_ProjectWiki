"""Evaluation script for RepoSum.

Decodes the test split of a trained checkpoint with beam search, computes
corpus-level BLEU-4 with a 95% bootstrap confidence interval, and records the
result as one row of results/main_results.csv (one row per method and setting).

Usage:
    python src/evaluate.py --config CONFIG --ckpt checkpoints/best.pt
"""
import argparse
import csv
import math
import os
from collections import Counter

import numpy as np
import torch

from reposum_model import RepoSumModel
from data import load_config, load_split, make_loader, get_tokenizer

FIELDS = ["method", "setting", "bleu4", "ci_low", "ci_high"]
N_BOOT = 1000
SEED = 13
MAX_SUMMARY_LEN = 48


def ngram_counts(tokens, n):
    return Counter(tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1))


def sentence_stats(hyp, ref):
    """Clipped n-gram matches and totals per order, plus hypothesis/reference lengths."""
    match, total = np.zeros(4), np.zeros(4)
    for n in range(1, 5):
        h, r = ngram_counts(hyp, n), ngram_counts(ref, n)
        match[n - 1] = sum(min(c, r[g]) for g, c in h.items())
        total[n - 1] = max(len(hyp) - n + 1, 0)
    return np.concatenate([match, total, [len(hyp), len(ref)]])


def bleu_from_stats(s):
    match, total = s[:4], s[4:8]
    hyp_len, ref_len = s[8], s[9]
    if match.min() == 0 or hyp_len == 0:
        return 0.0
    log_p = np.mean(np.log(match / total))
    bp = 1.0 if hyp_len > ref_len else math.exp(1 - ref_len / hyp_len)
    return 100.0 * bp * math.exp(log_p)


def bootstrap_ci(stats):
    """Resample functions with replacement and recompute corpus BLEU-4."""
    rng = np.random.default_rng(SEED)
    n = stats.shape[0]
    scores = [bleu_from_stats(stats[rng.integers(0, n, n)].sum(axis=0))
              for _ in range(N_BOOT)]
    return float(np.percentile(scores, 2.5)), float(np.percentile(scores, 97.5))


@torch.no_grad()
def decode_split(model, loader, tokenizer, device, beam_size):
    model.eval()
    hyps, refs = [], []
    for batch in loader:
        batch = {k: (v.to(device) if torch.is_tensor(v) else v) for k, v in batch.items()}
        out = model.generate(batch, beam_size=beam_size, max_len=MAX_SUMMARY_LEN)
        hyps += tokenizer.batch_decode(out, skip_special_tokens=True)
        refs += batch["summary"]
    return hyps, refs


def update_results(path, row):
    """Replace the row for (method, setting) if present, otherwise append it."""
    rows = []
    if os.path.exists(path):
        with open(path, newline="") as f:
            rows = [r for r in csv.DictReader(f)
                    if (r["method"], r["setting"]) != (row["method"], row["setting"])]
    rows.append(row)
    rows.sort(key=lambda r: (r["setting"], r["method"]))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description="Evaluate a RepoSum checkpoint")
    ap.add_argument("--config", required=True)
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--out", default="results/main_results.csv")
    args = ap.parse_args()

    torch.manual_seed(SEED)
    cfg = load_config(args.config)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = get_tokenizer(cfg)

    model = RepoSumModel(cfg["model"]).to(device)
    state = torch.load(args.ckpt, map_location=device)
    model.load_state_dict(state["model"])

    test_set = load_split(cfg, split="test")
    loader = make_loader(test_set, batch_size=64, shuffle=False)
    beam_size = cfg.get("decode", {}).get("beam_size", 5)
    hyps, refs = decode_split(model, loader, tokenizer, device, beam_size)

    stats = np.stack([sentence_stats(h.split(), r.split()) for h, r in zip(hyps, refs)])
    score = bleu_from_stats(stats.sum(axis=0))
    ci_low, ci_high = bootstrap_ci(stats)

    row = {
        "method": cfg.get("method", "RepoSum"),
        "setting": cfg["data"]["split"],
        "bleu4": f"{score:.1f}",
        "ci_low": f"{ci_low:.1f}",
        "ci_high": f"{ci_high:.1f}",
    }
    update_results(args.out, row)
    print(f"{row['method']} [{row['setting']}] BLEU-4 {row['bleu4']} "
          f"[{row['ci_low']}, {row['ci_high']}] over {len(hyps)} functions")


if __name__ == "__main__":
    main()
