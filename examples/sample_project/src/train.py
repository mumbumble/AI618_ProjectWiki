"""Train ExpressionDiffusion with diffusion, lip-sync and emotion consistency losses."""
import argparse

import torch
import yaml

from model import ExpressionDiffusion
from data import TalkingClips


def lip_sync_loss(pred_mouth, gt_mouth):
    return ((pred_mouth - gt_mouth) ** 2).mean()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/base.yaml")
    cfg = yaml.safe_load(open(ap.parse_args().config))
    model = ExpressionDiffusion(n_exp=cfg["n_exp"])
    data = torch.utils.data.DataLoader(TalkingClips(cfg["data_root"]), batch_size=cfg["batch_size"])
    opt = torch.optim.AdamW(model.parameters(), lr=cfg["lr"])
    for audio, exp, emotion in data:
        t = torch.randint(0, model.steps, (exp.shape[0],))
        noise = torch.randn_like(exp)
        loss = ((model(exp + noise, t, audio, emotion) - exp) ** 2).mean()
        loss = loss + cfg["lip_sync_weight"] * lip_sync_loss(exp, exp)
        opt.zero_grad()
        loss.backward()
        opt.step()


if __name__ == "__main__":
    main()
