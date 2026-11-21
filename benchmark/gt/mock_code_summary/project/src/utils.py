"""Shared helpers for RepoSum: seeding, logging and checkpoints."""
import logging
import os
import random
import sys

import numpy as np
import torch

DEFAULT_SEED = 13
LOG_FORMAT = "%(asctime)s %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def set_seed(seed: int = DEFAULT_SEED) -> None:
    """Seed Python, NumPy and PyTorch so that runs are repeatable."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def get_logger(name: str = "reposum", log_file: str | None = None) -> logging.Logger:
    """Return a logger that prints to stdout and, optionally, appends to log_file.

    The caller picks the file name (for example one file per training day),
    so this helper does not build any dated paths itself.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured by an earlier call
    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(formatter)
    logger.addHandler(stream)

    if log_file is not None:
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    return logger


def save_checkpoint(
    path: str,
    model: torch.nn.Module,
    optimizer: torch.optim.Optimizer | None = None,
    epoch: int = 0,
    step: int = 0,
    best_bleu4: float = 0.0,
    extra: dict | None = None,
) -> None:
    """Write model (and optimizer) state to path, creating parent folders.

    The file is written to a temporary name first and then renamed, so an
    interrupted save never leaves a half-written best.pt behind.
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    state = {
        "model": model.state_dict(),
        "optimizer": optimizer.state_dict() if optimizer is not None else None,
        "epoch": epoch,
        "step": step,
        "best_bleu4": best_bleu4,
        "extra": extra or {},
    }
    tmp_path = path + ".tmp"
    torch.save(state, tmp_path)
    os.replace(tmp_path, path)


def load_checkpoint(
    path: str,
    model: torch.nn.Module,
    optimizer: torch.optim.Optimizer | None = None,
    map_location: str = "cpu",
) -> dict:
    """Load weights into model (and optimizer if given).

    Returns the saved metadata (epoch, step, best_bleu4, extra) so the
    caller can resume counting or report which checkpoint was used.
    """
    state = torch.load(path, map_location=map_location)
    model.load_state_dict(state["model"])
    if optimizer is not None and state.get("optimizer") is not None:
        optimizer.load_state_dict(state["optimizer"])
    return {k: v for k, v in state.items() if k not in ("model", "optimizer")}
