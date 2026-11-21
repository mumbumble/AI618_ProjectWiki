"""Seeding, logging and checkpoint helpers for the ProsodySER experiments."""

import logging
import os
import random

import numpy as np
import torch
import yaml


def set_seed(seed: int = 1234) -> None:
    """Seed Python, NumPy and PyTorch (CPU and CUDA) for reproducible runs."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def get_logger(name: str, log_file: str, level: int = logging.INFO) -> logging.Logger:
    """Return a logger that writes to the console and to log_file.

    The caller decides the file name, e.g. a dated file inside the logs folder.
    Calling it twice with the same name does not add duplicate handlers.
    """
    os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if logger.handlers:
        return logger

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%Y-%m-%d %H:%M:%S")

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(fmt)
    logger.addHandler(stream_handler)
    return logger


def _deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: str) -> dict:
    """Load a YAML config and resolve the optional `inherits` key.

    A child config names its parent file in `inherits`. The parent is read
    first (relative to the child's folder) and the child values override it.
    Chains of inheritance are followed recursively.
    """
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    parent_name = cfg.pop("inherits", None)
    if parent_name is None:
        return cfg

    parent_path = os.path.join(os.path.dirname(path), parent_name)
    parent_cfg = load_config(parent_path)
    return _deep_merge(parent_cfg, cfg)


def save_checkpoint(path, model, optimizer=None, scheduler=None,
                    epoch: int = 0, best_ua: float = 0.0, extra=None) -> str:
    """Save model, optimizer and scheduler state plus training bookkeeping."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    state = {
        "epoch": epoch,
        "best_ua": best_ua,
        "model": model.state_dict(),
        "optimizer": optimizer.state_dict() if optimizer is not None else None,
        "scheduler": scheduler.state_dict() if scheduler is not None else None,
        "extra": extra or {},
    }
    torch.save(state, path)
    return path


def load_checkpoint(path, model=None, optimizer=None, scheduler=None, device="cpu") -> dict:
    """Load a checkpoint written by save_checkpoint and restore what is passed in.

    Returns the full state dict so the caller can read epoch, best_ua and extra.
    """
    state = torch.load(path, map_location=device)

    if model is not None:
        model.load_state_dict(state["model"])
    if optimizer is not None and state.get("optimizer") is not None:
        optimizer.load_state_dict(state["optimizer"])
    if scheduler is not None and state.get("scheduler") is not None:
        scheduler.load_state_dict(state["scheduler"])
    return state
