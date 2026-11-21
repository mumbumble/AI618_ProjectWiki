"""Training entry point for RepoSum.

Reads a YAML config (configs/base.yaml holds the defaults), builds the data
loaders and the model, trains with L = L_ce + lambda * L_ret and writes a
training log to logs/train_<date>.log.

Example:
    python src/train.py --config configs/intra_repo_java.yaml
"""
import argparse
import os
from datetime import datetime

import torch
import yaml

from data import build_loaders, bleu4_corpus
from reposum_model import RepoSumModel
from utils import set_seed, get_logger, save_checkpoint, load_checkpoint

LOG_EVERY = 200


def merge(base, over):
    out = dict(base)
    for key, val in over.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = merge(out[key], val)
        else:
            out[key] = val
    return out


def load_config(path):
    with open(path) as f:
        cfg = yaml.safe_load(f) or {}
    parent = cfg.pop("inherits", None)
    if parent is not None:
        base = load_config(os.path.join(os.path.dirname(path), parent))
        cfg = merge(base, cfg)
    return cfg


@torch.no_grad()
def dev_bleu4(model, loader, tokenizer, beam, device):
    model.eval()
    hyps, refs = [], []
    for batch in loader:
        refs.extend(batch.pop("summary_text"))
        tensors = {k: v.to(device) for k, v in batch.items()}
        preds = model.generate(tensors, beam_size=beam)
        hyps.extend(tokenizer.decode(p) for p in preds)
    return bleu4_corpus(hyps, refs)


def train_epoch(model, loader, optimizer, scheduler, cfg, device, log, state):
    lam = cfg["train"]["lambda_ret"]
    model.train()
    for batch in loader:
        batch = {k: v.to(device) for k, v in batch.items() if torch.is_tensor(v)}
        out = model(batch)
        loss = out["ce"] + lam * out["ret"]

        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        scheduler.step()
        state["step"] += 1

        if state["step"] % LOG_EVERY == 0:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log.info("%s step %d loss %.3f ce %.3f ret %.3f",
                     now, state["step"], loss.item(), out["ce"].item(), out["ret"].item())


def main():
    parser = argparse.ArgumentParser(description="Train RepoSum")
    parser.add_argument("--config", default="configs/base.yaml")
    parser.add_argument("--resume", default=None, help="checkpoint to resume from")
    args = parser.parse_args()

    cfg = load_config(args.config)
    tcfg = cfg["train"]
    set_seed(tcfg["seed"])
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    run_date = datetime.now().strftime("%Y-%m-%d")
    os.makedirs("logs", exist_ok=True)
    log = get_logger("train", os.path.join("logs", f"train_{run_date}.log"))
    log.info("config: %s", args.config)

    train_dl, dev_dl, tokenizer = build_loaders(cfg)
    model = RepoSumModel(cfg, vocab_size=tokenizer.vocab_size).to(device)
    optimizer = torch.optim.AdamW(model.parameters(),
                                  lr=tcfg["lr"], weight_decay=tcfg["weight_decay"])
    warmup = tcfg["warmup_steps"]
    scheduler = torch.optim.lr_scheduler.LambdaLR(
        optimizer, lambda s: min(1.0, (s + 1) / warmup))

    state = {"step": 0, "epoch": 0, "best": -1.0}
    if args.resume:
        ckpt = load_checkpoint(args.resume, model, optimizer)
        state.update(step=ckpt["step"], epoch=ckpt["epoch"], best=ckpt["best"])
        log.info("resumed from %s at epoch %d", args.resume, state["epoch"])

    os.makedirs("checkpoints", exist_ok=True)
    for epoch in range(state["epoch"] + 1, tcfg["epochs"] + 1):
        state["epoch"] = epoch
        train_epoch(model, train_dl, optimizer, scheduler, cfg, device, log, state)
        score = dev_bleu4(model, dev_dl, tokenizer, beam=1, device=device)
        if score > state["best"]:
            state["best"] = score
            save_checkpoint("checkpoints/best.pt", model, optimizer, state)
        log.info("epoch %d dev_bleu4 %.1f best %.1f", epoch, score, state["best"])

    log.info("done")


if __name__ == "__main__":
    main()
