"""Seeding, logging and checkpoint helpers shared by the LeafProto scripts."""

import logging
import os
import random
from datetime import datetime

import numpy as np
import torch
import yaml


def set_seed(seed: int = 42) -> None:
    """Fix python, numpy and torch RNGs so episodes are reproducible."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def get_logger(log_dir: str = "logs") -> logging.Logger:
    """Return a logger writing to logs/train_YYYY-MM-DD.log and to stdout."""
    os.makedirs(log_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d")
    log_path = os.path.join(log_dir, f"train_{stamp}.log")

    logger = logging.getLogger("leafproto")
    if logger.handlers:  # avoid duplicate handlers when called twice
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False
    fmt = logging.Formatter("[%(asctime)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(fmt)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def save_checkpoint(state: dict, path: str) -> None:
    """Save model/optimizer state and metadata, creating the folder if needed."""
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    torch.save(state, path)


def load_checkpoint(path: str, device: str = "cpu") -> dict:
    """Load a checkpoint saved by save_checkpoint."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"checkpoint not found: {path}")
    return torch.load(path, map_location=device)


def load_config(path: str) -> dict:
    """Load a YAML config and merge the parent named under the 'inherits' key.

    The parent path is resolved relative to the folder of the child config.
    Keys in the child override keys in the parent. Chains are followed.
    """
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    parent_name = cfg.pop("inherits", None)
    if parent_name is None:
        return cfg

    parent_path = os.path.join(os.path.dirname(path), parent_name)
    parent = load_config(parent_path)
    parent.update(cfg)
    return parent
