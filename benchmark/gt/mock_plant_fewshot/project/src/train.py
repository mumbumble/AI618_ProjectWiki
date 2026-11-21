"""Train LeafProto on the base classes of leafdoc_fs with episodic sampling.

Usage:
    python src/train.py --config configs/base.yaml
"""
import argparse
import time
from pathlib import Path

import torch
import torch.nn.functional as F

from leafproto_model import LeafProtoNet
from data import get_split, EpisodeSampler
from utils import set_seed, get_logger, save_checkpoint, load_config

VAL_EPISODES = 200
LOG_EVERY = 100


def parse_args():
    p = argparse.ArgumentParser(description="Train LeafProto (few-shot leaf disease)")
    p.add_argument("--config", default="configs/base.yaml", help="path to YAML config")
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    return p.parse_args()


def episode_loss(model, batch, lambda_cons):
    """Cross-entropy on clean query logits plus KL(clean || FreqMix view)."""
    sx, sy, qx, qy = batch
    logits_clean, logits_mix = model.episode_logits(sx, sy, qx)
    l_ce = F.cross_entropy(logits_clean, qy)
    p_clean = F.softmax(logits_clean, dim=1).detach()  # clean view is the target
    l_cons = F.kl_div(F.log_softmax(logits_mix, dim=1), p_clean, reduction="batchmean")
    return l_ce + lambda_cons * l_cons


@torch.no_grad()
def validate(model, sampler, dataset, device):
    model.eval()
    accs = []
    for sx, sy, qx, qy in sampler.iter_episodes(dataset, VAL_EPISODES, num_workers=0):
        logits = model.predict(sx.to(device), sy.to(device), qx.to(device))
        accs.append((logits.argmax(dim=1).cpu() == qy).float().mean().item())
    model.train()
    return sum(accs) / max(len(accs), 1)


def main():
    args = parse_args()
    cfg = load_config(args.config)
    set_seed(cfg["seed"])
    log = get_logger(cfg["log_dir"])
    log.info(f"config: {args.config}")
    device = torch.device(args.device)

    train_set = get_split("train", image_size=cfg["image_size"])
    val_set = get_split("val", image_size=cfg["image_size"])
    sampler = EpisodeSampler(cfg["n_way"], cfg["k_shot"], cfg["n_query"])

    model = LeafProtoNet(
        scale_init=cfg["scale_init"],
        freqmix_beta=cfg["freqmix"]["beta"],
        freqmix_p=cfg["freqmix"]["p"],
    ).to(device)
    optim = torch.optim.Adam(model.parameters(), lr=cfg["lr"], weight_decay=cfg["weight_decay"])
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(optim, T_max=cfg["episodes"])

    ckpt_path = Path("checkpoints") / "best.pt"
    ckpt_path.parent.mkdir(parents=True, exist_ok=True)
    best_acc, best_step = 0.0, 0
    running, count = 0.0, 0
    start = time.time()

    episodes = sampler.iter_episodes(train_set, cfg["episodes"], num_workers=cfg["num_workers"])
    for step, batch in enumerate(episodes, start=1):
        batch = [t.to(device, non_blocking=True) for t in batch]
        loss = episode_loss(model, batch, cfg["lambda_cons"])
        optim.zero_grad(set_to_none=True)
        loss.backward()
        optim.step()
        sched.step()
        running += loss.item()
        count += 1

        if step % cfg["eval_every"] == 0:
            acc = validate(model, sampler, val_set, device)
            log.info(f"step {step} loss {running / count:.3f} val_acc {acc:.3f}")
            running, count = 0.0, 0
            if acc > best_acc:
                best_acc, best_step = acc, step
                save_checkpoint(ckpt_path, model, optim, step, best_acc)
        elif step % LOG_EVERY == 0:
            log.info(f"step {step} loss {running / count:.3f} lr {sched.get_last_lr()[0]:.6f}")
            running, count = 0.0, 0

    elapsed = int(time.time() - start)
    h, rem = divmod(elapsed, 3600)
    m, s = divmod(rem, 60)
    log.info(f"done: best val_acc {best_acc:.3f} at step {best_step}, "
             f"total {h}h {m}m {s}s")


if __name__ == "__main__":
    main()
