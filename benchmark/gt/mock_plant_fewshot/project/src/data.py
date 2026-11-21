"""Dataset loading, episode sampling and split access for leafdoc_fs."""

import os
import random
from collections import defaultdict

import numpy as np
import pandas as pd
import torch
from PIL import Image
from torch.utils.data import Dataset

DATA_ROOT = os.path.join("data", "leafdoc_fs")
META_CSV = os.path.join(DATA_ROOT, "metadata.csv")
IMAGE_SIZE = 84
VALID_SPLITS = ("train", "val", "test")
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


def load_image(path):
    """Read a field photo, resize to 84x84 and return a normalised CHW tensor."""
    img = Image.open(path).convert("RGB")
    img = img.resize((IMAGE_SIZE, IMAGE_SIZE), Image.BILINEAR)
    arr = np.asarray(img, dtype=np.float32) / 255.0
    arr = (arr - MEAN) / STD
    return torch.from_numpy(arr.transpose(2, 0, 1).copy())


class LeafDocDataset(Dataset):
    """Leaf photos of one split, read from the metadata CSV.

    Columns used: image_path, label, species, disease, split.
    """

    def __init__(self, split, root=DATA_ROOT, meta_csv=META_CSV):
        if split not in VALID_SPLITS:
            raise ValueError(f"split must be one of {VALID_SPLITS}, got {split!r}")
        meta = pd.read_csv(meta_csv)
        meta = meta[meta["split"] == split].reset_index(drop=True)
        self.split = split
        self.root = root
        self.paths = meta["image_path"].tolist()
        self.labels = meta["label"].astype(int).tolist()
        self.species = meta["species"].tolist()
        self.disease = meta["disease"].tolist()
        self.index_by_class = defaultdict(list)
        for i, y in enumerate(self.labels):
            self.index_by_class[y].append(i)
        self.class_ids = sorted(self.index_by_class)

    def __len__(self):
        return len(self.paths)

    def __getitem__(self, idx):
        image = load_image(os.path.join(self.root, self.paths[idx]))
        return image, self.labels[idx]

    def num_classes(self):
        return len(self.class_ids)


class EpisodeSampler:
    """Draws N-way K-shot episodes with n_query queries per class.

    Support and query labels are remapped to 0..n_way-1 so that the
    prototype head always sees a consistent label space.
    """

    def __init__(self, n_way=5, k_shot=1, n_query=15, seed=42):
        self.n_way = n_way
        self.k_shot = k_shot
        self.n_query = n_query
        self.rng = random.Random(seed)

    def sample(self, dataset):
        need = self.k_shot + self.n_query
        eligible = [c for c in dataset.class_ids if len(dataset.index_by_class[c]) >= need]
        if len(eligible) < self.n_way:
            raise RuntimeError(f"only {len(eligible)} classes have {need} images")
        chosen = self.rng.sample(eligible, self.n_way)
        ep = {"support_idx": [], "support_y": [], "query_idx": [], "query_y": []}
        for new_label, c in enumerate(chosen):
            idx = self.rng.sample(dataset.index_by_class[c], need)
            ep["support_idx"] += idx[: self.k_shot]
            ep["support_y"] += [new_label] * self.k_shot
            ep["query_idx"] += idx[self.k_shot:]
            ep["query_y"] += [new_label] * self.n_query
        return ep

    def episodes(self, dataset, n_episodes):
        for _ in range(n_episodes):
            yield self.sample(dataset)


def load_episode(dataset, episode):
    """Turn episode indices into tensors (support_x, support_y, query_x, query_y)."""
    s_x = torch.stack([dataset[i][0] for i in episode["support_idx"]])
    q_x = torch.stack([dataset[i][0] for i in episode["query_idx"]])
    s_y = torch.tensor(episode["support_y"], dtype=torch.long)
    q_y = torch.tensor(episode["query_y"], dtype=torch.long)
    return s_x, s_y, q_x, q_y


def get_split(split, root=DATA_ROOT, meta_csv=META_CSV):
    return LeafDocDataset(split, root=root, meta_csv=meta_csv)


if __name__ == "__main__":
    for name in VALID_SPLITS:
        ds = get_split(name)
        print(f"{name}: {len(ds)} images, {ds.num_classes()} classes")
