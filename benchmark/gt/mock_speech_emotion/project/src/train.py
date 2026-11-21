"""Training script for ProsodySER on the KoEn-Emo corpus.

Usage:
    python src/train.py --config configs/base.yaml
    python src/train.py --config configs/bilingual_6class.yaml
"""
import argparse
import math
import os
import time

import numpy as np
import torch
import torch.nn.functional as F
from torch.optim.lr_scheduler import LambdaLR

from prosody_ser_model import ProsodySER
from data import make_loaders
from utils import set_seed, get_logger, save_checkpoint, load_config


def unweighted_accuracy(y_true, y_pred, n_classes=6):
    """UA = mean per-class recall, reported in percent."""
    recalls = []
    for c in range(n_classes):
        mask = y_true == c
        if mask.sum() > 0:
            recalls.append((y_pred[mask] == c).mean())
    return 100.0 * float(np.mean(recalls))


def grl_schedule(step, steps_per_epoch, ramp_epochs=5):
    """DANN-style ramp of the gradient reversal strength from 0 to 1."""
    p = min(1.0, step / float(ramp_epochs * steps_per_epoch))
    return 2.0 / (1.0 + math.exp(-10.0 * p)) - 1.0


def build_scheduler(optimizer, total_steps, warmup_steps):
    """Linear warmup followed by cosine decay."""
    def lr_lambda(step):
        if step < warmup_steps:
            return (step + 1) / warmup_steps
        progress = (step - warmup_steps) / max(1, total_steps - warmup_steps)
        return 0.5 * (1.0 + math.cos(math.pi * min(1.0, progress)))
    return LambdaLR(optimizer, lr_lambda)


@torch.no_grad()
def evaluate(model, loader, device):
    model.eval()
    preds, labels = [], []
    for batch in loader:
        batch = {k: v.to(device) for k, v in batch.items()}
        out = model(batch, grl_lambda=0.0)
        preds.append(out["emo_logits"].argmax(-1).cpu().numpy())
        labels.append(batch["emotion"].cpu().numpy())
    model.train()
    return unweighted_accuracy(np.concatenate(labels), np.concatenate(preds))


def train(cfg, config_path, logger):
    set_seed(cfg["seed"])
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    train_loader, val_loader, _ = make_loaders(cfg)

    model = ProsodySER(cfg).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=cfg["lr"],
                                  weight_decay=cfg["weight_decay"])
    steps_per_epoch = len(train_loader)
    total_steps = steps_per_epoch * cfg["epochs"]
    scheduler = build_scheduler(optimizer, total_steps, cfg["warmup_steps"])
    n_params = sum(p.numel() for p in model.parameters()) / 1e6

    logger.info(f"config={config_path} seed={cfg['seed']} device={device} "
                f"params={n_params:.1f}M")
    logger.info(f"steps_per_epoch={steps_per_epoch} total_steps={total_steps}")

    ckpt_path = os.path.join("checkpoints", f"{cfg.get('experiment_name', 'prosody_ser')}_best.pt")
    best_ua, step = -1.0, 0
    for epoch in range(1, cfg["epochs"] + 1):
        for batch in train_loader:
            batch = {k: v.to(device) for k, v in batch.items()}
            grl = grl_schedule(step, steps_per_epoch)
            out = model(batch, grl_lambda=grl)

            loss_ce = F.cross_entropy(out["emo_logits"], batch["emotion"],
                                      label_smoothing=cfg["label_smoothing"])
            loss_lang = F.cross_entropy(out["lang_logits"], batch["lang"])
            loss = loss_ce + cfg["lang_loss_weight"] * loss_lang

            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), cfg["grad_clip"])
            optimizer.step()
            scheduler.step()
            step += 1

            if step % 100 == 0:
                lr = scheduler.get_last_lr()[0]
                logger.info(f"step {step} epoch {epoch} loss {loss.item():.3f} "
                            f"lr {lr:.2e} grl {grl:.3f}")

        val_ua = evaluate(model, val_loader, device)
        logger.info(f"epoch {epoch} val_ua {val_ua:.1f}")
        if val_ua > best_ua:
            best_ua = val_ua
            save_checkpoint(ckpt_path, model=model, optimizer=optimizer,
                            epoch=epoch, metric=val_ua)
            logger.info(f"saved best checkpoint to {ckpt_path}")

    logger.info(f"done best_val_ua {best_ua:.1f}")


def main():
    parser = argparse.ArgumentParser(description="Train ProsodySER")
    parser.add_argument("--config", default="configs/base.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)
    date = time.strftime("%Y-%m-%d")
    os.makedirs("logs", exist_ok=True)
    os.makedirs("checkpoints", exist_ok=True)
    logger = get_logger(f"logs/train_{date}.log")
    logger.info(f"start {time.strftime('%H:%M:%S')}")
    train(cfg, args.config, logger)


if __name__ == "__main__":
    main()
