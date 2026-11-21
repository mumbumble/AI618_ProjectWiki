"""Evaluate a trained LeafProto checkpoint on the novel test split.

Runs 600 fixed-seed 5-way test episodes, reports mean accuracy and the
95% confidence interval over episodes, and records the row in the
main results table.
"""
import argparse
import math
import os

import numpy as np
import pandas as pd
import torch
import yaml

from leafproto_model import LeafProtoNet
from data import get_split, EpisodeSampler

RESULTS_CSV = "results/main_results.csv"
N_TEST_EPISODES = 600
RESULT_COLS = ["method", "shots", "accuracy", "ci95"]


def load_config(path):
    with open(path, "r") as f:
        cfg = yaml.safe_load(f)
    parent = cfg.pop("inherits", None)
    if parent:
        base = load_config(os.path.join(os.path.dirname(path), parent))
        base.update(cfg)
        cfg = base
    return cfg


def set_seed(seed):
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


@torch.no_grad()
def run_episodes(model, dataset, sampler, device, n_episodes):
    model.eval()
    accs = []
    for _ in range(n_episodes):
        xs, ys, xq, yq = sampler.sample(dataset)
        logits = model(xs.to(device), ys.to(device), xq.to(device))
        pred = logits.argmax(dim=1).cpu()
        accs.append((pred == yq).float().mean().item() * 100.0)
    return np.array(accs)


def upsert_result(path, row):
    if os.path.exists(path):
        df = pd.read_csv(path)
    else:
        df = pd.DataFrame(columns=RESULT_COLS)
    mask = (df["method"] == row["method"]) & (df["shots"] == row["shots"])
    df = pd.concat([df[~mask], pd.DataFrame([row])], ignore_index=True)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False)


def main():
    parser = argparse.ArgumentParser(description="Evaluate LeafProto on test episodes")
    parser.add_argument("--config", required=True)
    parser.add_argument("--ckpt", required=True)
    parser.add_argument("--method", default="LeafProto")
    args = parser.parse_args()

    cfg = load_config(args.config)
    set_seed(cfg["seed"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model = LeafProtoNet(scale_init=cfg["scale_init"]).to(device)
    ckpt = torch.load(args.ckpt, map_location=device)
    model.load_state_dict(ckpt.get("model", ckpt))
    print(f"loaded {args.ckpt} (step {ckpt.get('step', 'unknown')})")

    dataset = get_split("test")
    sampler = EpisodeSampler(cfg["n_way"], cfg["k_shot"], cfg["n_query"])
    accs = run_episodes(model, dataset, sampler, device, N_TEST_EPISODES)

    mean = accs.mean()
    ci95 = 1.96 * accs.std(ddof=1) / math.sqrt(len(accs))
    print(f"{args.method} {cfg['k_shot']}-shot: {mean:.1f} +- {ci95:.1f} "
          f"(ci95 over {len(accs)} episodes)")

    row = {
        "method": args.method,
        "shots": cfg["k_shot"],
        "accuracy": round(mean, 1),
        "ci95": round(ci95, 1),
    }
    upsert_result(RESULTS_CSV, row)
    print(f"wrote {RESULTS_CSV}")


if __name__ == "__main__":
    main()
