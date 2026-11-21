"""Training entry point for GraspDR.

Reads a YAML config (inherits chains are resolved by load_config), builds the
object datasets, the structured randomizer and the GraspPolicy, then runs PPO
with the contact auxiliary loss and the range curriculum.

Usage:
    python src/train.py --config configs/base.yaml
"""
import argparse
import time
from datetime import datetime
from pathlib import Path

import torch
from torch.optim import Adam

from graspdr_policy import GraspPolicy
from data import StructuredRandomizer, build_datasets
from utils import load_config, set_seed, make_logger

ROLLOUT_STEPS = 32
MINIBATCH = 4096
CLIP = 0.2
GAE_LAMBDA = 0.95
VF_COEF = 0.5
ENT_COEF = 0.01
LOG_EVERY = 500_000


def curriculum_scale(step, cfg):
    """Ramp the randomization scale s linearly from s_start to 1.0."""
    frac = min(1.0, step / cfg.curriculum_steps)
    return cfg.s_start + (1.0 - cfg.s_start) * frac


def compute_gae(rew, val, done, gamma, lam):
    """Generalized advantage estimation over time-major (T, N) tensors."""
    adv = torch.zeros_like(rew)
    gae = torch.zeros_like(val[0])
    for t in reversed(range(rew.shape[0])):
        nonterm = 1.0 - done[t]
        delta = rew[t] + gamma * val[t + 1] * nonterm - val[t]
        gae = delta + gamma * lam * nonterm * gae
        adv[t] = gae
    return adv, adv + val[:-1]


def ppo_update(policy, optim, batch, cfg):
    n = batch["obs"].shape[0]
    perm = torch.randperm(n, device=batch["obs"].device)
    loss = torch.zeros(())
    for start in range(0, n, MINIBATCH):
        idx = perm[start:start + MINIBATCH]
        new_logp, new_val, ent, contact_logits = policy.evaluate(
            batch["obs"][idx], batch["act"][idx], batch["priv"][idx])
        ratio = torch.exp(new_logp - batch["logp"][idx])
        adv = batch["adv"][idx]
        adv = (adv - adv.mean()) / (adv.std() + 1e-8)
        surr = torch.min(ratio * adv, torch.clamp(ratio, 1 - CLIP, 1 + CLIP) * adv)
        pg_loss = -surr.mean()
        v_loss = (new_val - batch["ret"][idx]).pow(2).mean()
        aux = torch.nn.functional.binary_cross_entropy_with_logits(
            contact_logits, batch["contact"][idx])
        loss = pg_loss + VF_COEF * v_loss - ENT_COEF * ent.mean() + cfg.aux_weight * aux
        optim.zero_grad()
        loss.backward()
        optim.step()
    return loss.item()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/base.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)
    set_seed(cfg.seed)

    log_path = Path(datetime.now().strftime("logs/train_%Y-%m-%d.log"))
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger = make_logger(log_path)
    logger.info(f"config: {args.config}")

    train_meshes, val_meshes, _ = build_datasets(cfg.dataset)
    randomizer = StructuredRandomizer(rho=cfg.rho)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    policy = GraspPolicy(width=32, hidden=128).to(device)
    optim = Adam(policy.parameters(), lr=cfg.lr)

    ckpt_dir = Path("checkpoints")
    ckpt_dir.mkdir(exist_ok=True)
    step, best, next_log = 0, -1.0, LOG_EVERY
    t0 = time.time()

    while step < cfg.total_steps:
        s = curriculum_scale(step, cfg)
        theta = randomizer.sample(cfg.num_envs, scale=s, device=device)
        # rewards come from the contact-aware reward (lambda_c, lambda_f, f_max, f_min)
        batch = policy.collect(theta, ROLLOUT_STEPS, train_meshes, reward_cfg=cfg)
        adv, ret = compute_gae(batch["rew"], batch["val"], batch["done"], cfg.gamma, GAE_LAMBDA)
        batch.update(adv=adv, ret=ret)
        flat = {k: v.flatten(0, 1) for k, v in batch.items() if k != "val"}
        loss = ppo_update(policy, optim, flat, cfg)
        step += cfg.num_envs * ROLLOUT_STEPS

        if step >= next_log or step >= cfg.total_steps:
            val_success = policy.evaluate_success(val_meshes, randomizer, scale=1.0)
            logger.info(
                f"{datetime.now():%Y-%m-%d %H:%M:%S} step={step} loss={loss:.3f} "
                f"scale={s:.2f} val_success={val_success:.1f} "
                f"elapsed={time.time() - t0:.0f}s")
            next_log += LOG_EVERY
            if val_success > best:
                best = val_success
                torch.save({"model": policy.state_dict(), "step": step},
                           ckpt_dir / "best.pt")

    torch.save({"model": policy.state_dict(), "step": step}, ckpt_dir / "last.pt")
    logger.info(f"done: {step} env steps, best val_success={best:.1f}")


if __name__ == "__main__":
    main()
