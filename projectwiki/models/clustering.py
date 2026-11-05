"""Model stage 2 — clustering (experimental slot): group the files, optionally with the user's preferences.

A method is a class built as `Method(cfg)` with `cluster(record, prefs) -> list[Group]`. Add it here (or in any
module) and register it in CLUSTERERS, or pass `--clusterer package.module:Method`. Group names are filled in
afterwards by srcs/naming.py.

- baseline: control condition, no preference. Average-linkage clustering on bge-m3 + folder-tree distance.
- pref (11/05 meeting): important files seed groups (1안), 1-5 pair ratings fix pair distances,
  a multiple-choice guide sets how much the folder tree counts (3안).
"""
from __future__ import annotations

from typing import Protocol

import numpy as np
from sklearn.cluster import AgglomerativeClustering

from ..config import Config
from ..schema import Group, Preferences
from ..srcs.plugins import load_component
from ..srcs.record import Record


# ---- interface -----------------------------------------------------------------------------------


class Clusterer(Protocol):
    """Groups may leave out files (ungrouped nodes). Group names are filled in later when empty."""
    name: str

    def cluster(self, record: Record, prefs: Preferences) -> list[Group]: ...


# ---- baseline ------------------------------------------------------------------------------------


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


# ---- pref ----------------------------------------------------------------------------------------
GUIDE_ALPHA = {"folder": 0.2, "content": 0.9}
ANCHOR_PCT = 25.0  # a file joins its nearest anchor if closer than this percentile of distances


class PreferenceClusterer:
    name = "pref"

    def __init__(self, cfg: Config):
        self.alpha, self.pct = cfg.cluster_alpha, cfg.cluster_pct

    def cluster(self, record: Record, prefs: Preferences) -> list[Group]:
        files = record.files
        if len(files) < 3:
            return [Group(id="g1", name="", members=[f.id for f in files])]
        dist = mixed_distance(record, GUIDE_ALPHA.get(prefs.guide.get("group_by", ""), self.alpha))
        for p in prefs.pairs:
            a, b = record.resolve(p.get("a")), record.resolve(p.get("b"))
            if a and b and a != b:
                i, j = record.file_index[a], record.file_index[b]
                dist[i, j] = dist[j, i] = (5.0 - float(np.clip(p.get("score", 3), 1, 5))) / 4.0
        threshold = float(np.percentile(upper(dist), self.pct))

        anchors = list(dict.fromkeys(record.file_index[a] for a in map(record.resolve, prefs.anchors) if a))
        clusters = [[a] for a in anchors]
        rest = []
        if anchors:
            join = float(np.percentile(upper(dist), ANCHOR_PCT))
            for i in range(len(files)):
                if i in anchors:
                    continue
                k = int(np.argmin(dist[i, anchors]))
                if dist[i, anchors[k]] <= join:
                    clusters[k].append(i)
                else:
                    rest.append(i)
        else:
            rest = list(range(len(files)))
        if rest:
            sub = dist[np.ix_(rest, rest)]
            clusters += [[rest[j] for j in c] for c in agglomerate(sub, threshold)]
        return [Group(id=f"g{n + 1}", name="", members=[files[i].id for i in c]) for n, c in enumerate(clusters)]


# ---- registry ------------------------------------------------------------------------------------
CLUSTERERS = {"baseline": BaselineClusterer, "pref": PreferenceClusterer}


def get_clusterer(name: str, cfg: Config) -> Clusterer:
    return load_component(name, CLUSTERERS, cfg)
