"""Dataset loading, splits, and structured domain randomization (SRS) for GraspDR.

tabletop_objs_v2 has 800 object meshes in meshes/. split_train.json (640 meshes)
is used for training. split_val.json (80) and split_test.json (80) together make
up the 160 held-out meshes.
"""

import json
import os

import numpy as np

DATASET_ROOT = "data/tabletop_objs_v2"
SPLIT_FILES = {
    "train": "split_train.json",
    "val": "split_val.json",
    "test": "split_test.json",
}
EXPECTED_COUNTS = {"train": 640, "val": 80, "test": 80}


class ObjectMeshDataset:
    """Indexes the object meshes of one split of tabletop_objs_v2."""

    def __init__(self, root=DATASET_ROOT, split="train"):
        if split not in SPLIT_FILES:
            raise ValueError(f"unknown split: {split}")
        self.root = root
        self.split = split
        with open(os.path.join(root, SPLIT_FILES[split])) as f:
            self.records = json.load(f)
        if len(self.records) != EXPECTED_COUNTS[split]:
            raise ValueError(
                f"{split} has {len(self.records)} meshes, "
                f"expected {EXPECTED_COUNTS[split]}"
            )

    def __len__(self):
        return len(self.records)

    def __getitem__(self, idx):
        rec = self.records[idx]
        return {
            "id": rec["id"],
            "category": rec["category"],
            "mesh_path": os.path.join(self.root, "meshes", rec["mesh"]),
        }


def load_splits(root=DATASET_ROOT):
    """Return the train/val/test datasets and make sure they do not overlap."""
    splits = {name: ObjectMeshDataset(root, name) for name in SPLIT_FILES}
    seen = set()
    for name, ds in splits.items():
        ids = {rec["id"] for rec in ds.records}
        if ids & seen:
            raise RuntimeError(f"split '{name}' shares meshes with another split")
        seen |= ids
    return splits


# group -> {name: (nominal, half-range at s=1, lower bound or None)}
PARAM_SPECS = {
    "visual": {
        "light_intensity": (1.0, 0.3, 0.1),
        "texture_hue": (0.0, 0.05, None),
        "camera_jitter_cm": (0.0, 2.0, None),
    },
    "dynamics": {
        "friction": (0.8, 0.4, 0.05),        # 0.4 - 1.2
        "object_mass": (1.0, 0.3, 0.05),     # +-30 % multiplier
        "joint_damping": (1.0, 0.25, 0.05),  # +-25 % multiplier
    },
    "geometry": {
        "object_scale": (1.0, 0.2, 0.05),    # 0.8 - 1.2
        "pad_stiffness": (1.0, 0.2, 0.05),   # relative to nominal
    },
}


class StructuredRandomizer:
    """Grouped, correlated domain randomization (SRS).

    Each group g has a latent z_g ~ N(0, I) and parameters
        theta_g = mu_g + s * spread_g * (L_g @ z_g),
    where L_g is the Cholesky factor of a group correlation matrix with
    within-group correlation rho. Groups are sampled independently.
    """

    def __init__(self, rho=0.6, seed=0):
        self.rho = rho
        self.rng = np.random.default_rng(seed)
        self.names, self.chol, self.mu, self.spread, self.lower = {}, {}, {}, {}, {}
        for group, specs in PARAM_SPECS.items():
            k = len(specs)
            corr = np.full((k, k), rho)
            np.fill_diagonal(corr, 1.0)
            self.chol[group] = np.linalg.cholesky(corr)
            self.names[group] = list(specs)
            vals = list(specs.values())
            self.mu[group] = np.array([v[0] for v in vals])
            self.spread[group] = np.array([v[1] for v in vals])
            self.lower[group] = np.array(
                [v[2] if v[2] is not None else -np.inf for v in vals]
            )

    def sample(self, s=1.0):
        """Draw one set of physics and visual parameters at range scale s."""
        theta = {}
        for group in PARAM_SPECS:
            z = self.rng.standard_normal(len(self.names[group]))
            delta = s * self.spread[group] * (self.chol[group] @ z)
            values = np.maximum(self.mu[group] + delta, self.lower[group])
            theta.update(zip(self.names[group], values.tolist()))
        return theta


def range_scale(env_steps, s_start=0.5, s_end=1.0, ramp_steps=2_000_000):
    """Range Curriculum: ramp s linearly over the first ramp_steps env steps."""
    frac = min(max(env_steps / ramp_steps, 0.0), 1.0)
    return s_start + (s_end - s_start) * frac
