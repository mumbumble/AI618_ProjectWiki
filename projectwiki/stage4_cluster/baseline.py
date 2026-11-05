"""Control condition for stage 4: no user preference.

Average-linkage agglomerative clustering on a mix of bge-m3 cosine distance and folder-tree distance.
"""
from __future__ import annotations

import numpy as np
from sklearn.cluster import AgglomerativeClustering

from ..config import Config
from ..stage3_record import Record
from ..schema import Group, Preferences


def tree_distance(paths: list[str]) -> np.ndarray:
    """1 - shared directory depth / deeper directory depth; files in the same folder are 0."""
    dirs = [p.split("/")[:-1] for p in paths]
    n = len(dirs)
    d = np.zeros((n, n), np.float32)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = dirs[i], dirs[j]
            depth = max(len(a), len(b))
            common = next((k for k, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
            d[i, j] = d[j, i] = 0.0 if depth == 0 else 1.0 - common / depth
    return d


def mixed_distance(record: Record, alpha: float) -> np.ndarray:
    e = record.file_emb
    dist = alpha * np.clip(1.0 - e @ e.T, 0.0, 1.0) + (1 - alpha) * tree_distance([f.path for f in record.files])
    np.fill_diagonal(dist, 0.0)
    return dist


def agglomerate(dist: np.ndarray, threshold: float) -> list[list[int]]:
    """Average-linkage clusters of row indices, largest first."""
    if len(dist) < 2:
        return [list(range(len(dist)))] if len(dist) else []
    labels = AgglomerativeClustering(n_clusters=None, metric="precomputed", linkage="average",
                                     distance_threshold=threshold).fit_predict(dist)
    members: dict[int, list[int]] = {}
    for i, lab in enumerate(labels):
        members.setdefault(int(lab), []).append(i)
    return sorted(members.values(), key=len, reverse=True)


def upper(dist: np.ndarray) -> np.ndarray:
    return dist[np.triu_indices(len(dist), 1)]


class BaselineClusterer:
    name = "baseline"

    def __init__(self, cfg: Config):
        self.alpha, self.pct = cfg.cluster_alpha, cfg.cluster_pct

    def cluster(self, record: Record, prefs: Preferences) -> list[Group]:
        files = record.files
        if len(files) < 3:
            return [Group(id="g1", name="", members=[f.id for f in files])]
        dist = mixed_distance(record, self.alpha)
        clusters = agglomerate(dist, float(np.percentile(upper(dist), self.pct)))
        return [Group(id=f"g{i + 1}", name="", members=[files[j].id for j in c]) for i, c in enumerate(clusters)]
