"""Seeding, logging and checkpoint helpers for GraspDR training and evaluation."""

import logging
import os
import random
from datetime import datetime

import numpy as np
import torch


def seed_everything(seed: int, deterministic: bool = False) -> None:
    """Seed python, numpy and torch so runs are repeatable (we report seeds 0-4)."""
    os.environ["PYTHONHASHSEED"] = str(seed)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = not deterministic
    torch.backends.cudnn.deterministic = deterministic


def get_logger(name: str = "graspdr", log_dir: str = "logs") -> logging.Logger:
    """Console + file logger. File name follows logs/train_<YYYY-MM-DD>.log."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    os.makedirs(log_dir, exist_ok=True)
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_name = datetime.now().strftime("train_%Y-%m-%d.log")
    file_handler = logging.FileHandler(os.path.join(log_dir, file_name))
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    logger.addHandler(stream_handler)
    return logger


class AverageMeter:
    """Keeps a running mean, used for per-interval loss and success logging."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.total = 0.0
        self.count = 0

    def update(self, value: float, n: int = 1) -> None:
        self.total += float(value) * n
        self.count += n

    @property
    def avg(self) -> float:
        return self.total / max(self.count, 1)


def save_checkpoint(ckpt_dir, step, model, optimizer, config, metrics=None, is_best=False):
    """Write checkpoints/step_XXXXXXXXX.pt, and copy to checkpoints/best.pt if is_best."""
    os.makedirs(ckpt_dir, exist_ok=True)
    state = {
        "step": int(step),
        "model": model.state_dict(),
        "optimizer": optimizer.state_dict() if optimizer is not None else None,
        "config": dict(config),
        "metrics": metrics or {},
    }
    path = os.path.join(ckpt_dir, f"step_{step:09d}.pt")
    torch.save(state, path)
    if is_best:
        torch.save(state, os.path.join(ckpt_dir, "best.pt"))
    return path


def load_checkpoint(path, model=None, optimizer=None, map_location="cpu"):
    """Load a checkpoint and restore model / optimizer weights when they are given."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"checkpoint not found: {path}")
    state = torch.load(path, map_location=map_location)
    if model is not None:
        model.load_state_dict(state["model"])
    if optimizer is not None and state.get("optimizer") is not None:
        optimizer.load_state_dict(state["optimizer"])
    return state


def count_parameters(model) -> int:
    """Number of trainable parameters, printed at startup for the model summary."""
    return sum(p.numel() for p in model.parameters() if p.requires_grad)
