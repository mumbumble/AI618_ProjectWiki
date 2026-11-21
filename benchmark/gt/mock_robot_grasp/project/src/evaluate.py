"""Evaluate a trained GraspDR checkpoint across randomization range scales.

For each evaluation range, runs held-out grasp episodes with shifted physics,
reports the grasp success rate with a 95% normal-approximation confidence
interval, and writes the rows to results/main_results.csv.
"""
import argparse
import csv
import math
import os

import torch
import yaml

from graspdr_policy import GraspPolicy
from data import StructuredRandomizer, make_eval_env

COLUMNS = ["method", "randomization_range", "success_rate", "ci95_half_width", "n_episodes"]


def load_config(path):
    with open(path) as f:
        return yaml.safe_load(f)


def ci95_half_width(p, n):
    """Half-width of the 95% CI for a proportion p over n episodes, in percentage points."""
    return 1.96 * math.sqrt(p * (1.0 - p) / n) * 100.0


@torch.no_grad()
def count_successes(policy, env, n_episodes, device):
    """Roll out batches of parallel episodes until n_episodes have been scored."""
    scored, successes = 0, 0
    while scored < n_episodes:
        obs = env.reset()
        finished = torch.zeros(env.num_envs, dtype=torch.bool, device=device)
        success_now = torch.zeros_like(finished)
        while not bool(finished.all()):
            action = policy.act(obs)
            obs, _, done, info = env.step(action)
            newly = done & ~finished
            success_now[newly] = info["grasp_success"][newly]
            finished |= done
        take = min(env.num_envs, n_episodes - scored)
        successes += int(success_now[:take].sum())
        scored += take
    return successes, scored


def main():
    parser = argparse.ArgumentParser(description="Evaluate a GraspDR checkpoint.")
    parser.add_argument("--config", required=True, help="YAML config used for training")
    parser.add_argument("--ckpt", required=True, help="checkpoint path, e.g. checkpoints/best.pt")
    parser.add_argument("--method", default="GraspDR", help="method label written to the CSV")
    parser.add_argument("--n-episodes", type=int, default=2000, help="episodes per range")
    parser.add_argument("--out", default="results/main_results.csv")
    parser.add_argument("--append", action="store_true", help="append rows instead of overwriting")
    args = parser.parse_args()

    cfg = load_config(args.config)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    policy = GraspPolicy(cfg).to(device)
    state = torch.load(args.ckpt, map_location=device)
    policy.load_state_dict(state["policy"])
    policy.eval()

    randomizer = StructuredRandomizer(rho=cfg["rho"], seed=cfg["seed"])
    env = make_eval_env(cfg, randomizer)

    rows = []
    for s in cfg["eval_ranges"]:
        randomizer.set_scale(s)
        successes, n = count_successes(policy, env, args.n_episodes, device)
        p = successes / n
        rate, half = 100.0 * p, ci95_half_width(p, n)
        rows.append([args.method, f"{s:.1f}", f"{rate:.1f}", f"{half:.1f}", n])
        print(f"{args.method} range={s:.1f}: success {rate:.1f}% +- {half:.1f} (n={n})")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    write_header = not (args.append and os.path.exists(args.out))
    with open(args.out, "a" if args.append else "w", newline="") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(COLUMNS)
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
