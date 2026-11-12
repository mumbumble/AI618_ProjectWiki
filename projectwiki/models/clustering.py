"""Model stage 2 — clustering (experimental slot): group the files, optionally with the user's preferences.

A method is a class built as `Method(cfg)` with `cluster(record, prefs) -> list[Group]`. Add it here (or in any
module) and register it in CLUSTERERS, or pass `--clusterer package.module:Method`. Group names are filled in
afterwards by srcs/naming.py.

- baseline: control condition, no preference. Average-linkage clustering on bge-m3 + folder-tree distance.
- pref (11/05 meeting): important files seed groups (1안), 1-5 pair ratings fix pair distances,
  a multiple-choice guide sets how much the folder tree counts (3안).
- metric: learn nonnegative content/folder/type distance weights from grouping-preference ratings.
- constrained: average linkage with must-link/cannot-link ratings and separate anchors.
- graph: spectral communities from a similarity kNN graph plus imports and document links.
- hdbscan: dense groups with explicit noise/ungrouped files.
"""
from __future__ import annotations

import heapq
import logging
from dataclasses import replace
from typing import Protocol

import numpy as np
from sklearn.cluster import AgglomerativeClustering

from ..config import Config
from ..schema import Group, Preferences
from ..srcs.plugins import load_component
from ..srcs.record import Record

log = logging.getLogger(__name__)


# ---- interface -----------------------------------------------------------------------------------


class Clusterer(Protocol):
    """Groups may leave out files (ungrouped nodes). Group names are filled in later when empty."""
    name: str

    def cluster(self, record: Record, prefs: Preferences) -> list[Group]: ...


# ---- baseline ------------------------------------------------------------------------------------


def tree_distance(paths: list[str]) -> np.ndarray:
    """1 - shared directory depth / deeper directory depth; same-folder distance is 0.

    Project-defined folder heuristic, not a distance formula reproduced from the
    hierarchical-clustering references cited in agglomerate().
    """
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
    """Blend content and folder distances using a project-specific heuristic.

    The clipped cosine distance, this convex blend, and the default alpha=0.6
    are local design choices. The linkage reference in agglomerate() establishes
    the clustering algorithm, not the effectiveness of these features or weights.
    """
    e = record.file_emb
    dist = alpha * np.clip(1.0 - e @ e.T, 0.0, 1.0) + (1 - alpha) * tree_distance([f.path for f in record.files])
    np.fill_diagonal(dist, 0.0)
    return dist


def agglomerate(dist: np.ndarray, threshold: float) -> list[list[int]]:
    """Average-linkage clusters of row indices, largest first.

    Reference: D. Muellner (2011), "Modern hierarchical, agglomerative clustering
    algorithms", which discusses average linkage (UPGMA) and other linkage schemes.
    https://arxiv.org/abs/1109.2378
    Implementation: sklearn AgglomerativeClustering with precomputed distances.
    https://scikit-learn.org/stable/modules/generated/sklearn.cluster.AgglomerativeClustering.html

    The choice of a percentile-based cut is a project heuristic supplied by callers,
    not a threshold derived from this paper.
    """
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
        """Run the average-linkage control; see agglomerate() for its reference.

        The content/folder blend and the default 35th-percentile cut are our
        experimental baseline settings, not a reproduction of a published pipeline.
        """
        files = record.files
        if len(files) < 3:
            return [Group(id="g1", name="", members=[f.id for f in files])]
        dist = mixed_distance(record, self.alpha)
        clusters = agglomerate(dist, float(np.percentile(upper(dist), self.pct)))
        return [Group(id=f"g{i + 1}", name="", members=[files[j].id for j in c]) for i, c in enumerate(clusters)]


# ---- pref ----------------------------------------------------------------------------------------
GUIDE_ALPHA = {"folder": 0.2, "content": 0.9}
ANCHOR_PCT = 25.0  # a file joins its nearest anchor if closer than this percentile of distances


def preference_groups(record: Record, prefs: Preferences, dist: np.ndarray, pct: float) -> list[Group]:
    """Shared anchor assignment and average-linkage policy for pref and metric.

    Related work: S. Basu, A. Banerjee, R. J. Mooney (ICML 2002),
    "Semi-supervised Clustering by Seeding".
    https://www.cs.utexas.edu/~ai-lab/pub-view.php?PubID=51520

    This is the project's meeting-defined anchor heuristic, not that paper's
    Seeded/Constrained K-Means. One group per anchor, the 25th-percentile join
    radius, and clustering the remainder with average linkage are local choices.
    """
    files = record.files
    if len(files) < 3:
        return [Group(id="g1", name="", members=[f.id for f in files])]
    threshold = float(np.percentile(upper(dist), pct))
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


class PreferenceClusterer:
    name = "pref"

    def __init__(self, cfg: Config):
        self.alpha, self.pct = cfg.cluster_alpha, cfg.cluster_pct

    def distance_matrix(self, record: Record, prefs: Preferences) -> np.ndarray:
        """Apply local guide weights and direct pair-distance edits.

        Mapping a 1-5 grouping preference to (5-score)/4 and choosing guide alpha
        values 0.2/0.9 are project conventions, not rules from the seeding paper.
        See preference_groups() for the related literature and adaptation boundary.
        """
        dist = mixed_distance(record, GUIDE_ALPHA.get(prefs.guide.get("group_by", ""), self.alpha))
        for p in prefs.pairs:
            a, b = record.resolve(p.get("a")), record.resolve(p.get("b"))
            if a and b and a != b:
                i, j = record.file_index[a], record.file_index[b]
                dist[i, j] = dist[j, i] = (5.0 - float(np.clip(p.get("score", 3), 1, 5))) / 4.0
        self.distances_ = dist
        return dist

    def cluster(self, record: Record, prefs: Preferences) -> list[Group]:
        """Apply the meeting-defined pref method; references are in preference_groups()."""
        if len(record.files) < 3:
            return [Group(id="g1", name="", members=[f.id for f in record.files])]
        return preference_groups(record, prefs, self.distance_matrix(record, prefs), self.pct)


# ---- learned distance ----------------------------------------------------------------------------


def resolve_ratings(record: Record, pairs: list) -> tuple[list[dict], dict[str, int]]:
    """Validate grouping ratings; the last valid rating of an unordered pair wins."""
    unique = {}
    invalid, duplicates = 0, 0
    for n, pair in enumerate(pairs, 1):
        try:
            if not isinstance(pair, dict) or not all(isinstance(pair.get(k), str) for k in ("a", "b")):
                raise ValueError("expected file references a and b")
            a, b = record.resolve(pair["a"]), record.resolve(pair["b"])
            if a is None or b is None or a == b:
                raise ValueError("missing file or self-pair")
            if isinstance(pair.get("score"), bool):
                raise ValueError("score must be a number from 1 to 5")
            score = float(pair["score"])
            if not np.isfinite(score) or not 1 <= score <= 5:
                raise ValueError("score must be a finite number from 1 to 5")
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            invalid += 1
            log.warning("skipping grouping rating %d: %s", n, exc)
            continue
        key = tuple(sorted((a, b)))
        duplicates += int(key in unique)
        unique[key] = {"a": key[0], "b": key[1], "score": score}
    return list(unique.values()), {"received": len(pairs), "valid": len(unique),
                                   "invalid": invalid, "duplicates": duplicates}


def distance_features(record: Record, use_type: bool = True) -> np.ndarray:
    """Symmetric distance channels in [0, 1], without modifying stored embeddings.

    Content distance, folder distance and file-type mismatch are features selected
    for this project. The metric-learning paper in fit_distance_weights() motivates
    learning distances from supervision, but does not prescribe these features.
    """
    content = np.clip(1.0 - record.file_emb @ record.file_emb.T, 0.0, 1.0)
    np.fill_diagonal(content, 0.0)
    channels = [content, tree_distance([f.path for f in record.files])]
    if use_type:
        types = np.array([f.type for f in record.files])
        channels.append((types[:, None] != types[None, :]).astype(float))
    features = np.stack(channels, axis=-1).astype(float)
    if not np.isfinite(features).all():
        raise ValueError("file embeddings must contain only finite values")
    return features


def fit_distance_weights(x: np.ndarray, y: np.ndarray, prior: np.ndarray, l2: float) -> np.ndarray:
    """Minimize mean((Xw-y)^2) + l2*||w-prior||^2 on the probability simplex.

    With only two or three channels, enumerating every simplex face (at most seven)
    gives a deterministic solution of the small convex quadratic, using NumPy only.

    Related work: M. Bilenko, S. Basu, R. J. Mooney (ICML 2004),
    "Integrating Constraints and Metric Learning in Semi-Supervised Clustering".
    https://icml.cc/Conferences/2004/proceedings/papers/119.pdf

    The paper motivates adapting distances using supervision. This objective,
    its prior-centred L2 penalty and simplex-constrained feature weights are our
    small regression model, not MPCK-Means or full Mahalanobis metric learning.
    """
    n, dims = x.shape
    if not n:
        return prior.copy()
    h = x.T @ x / n + l2 * np.eye(dims)
    rhs = x.T @ y / n + l2 * prior

    def loss(w):
        return float(np.mean((x @ w - y) ** 2) + l2 * np.sum((w - prior) ** 2))

    best, best_loss = prior.copy(), loss(prior)
    for mask in range(1, 1 << dims):
        active = [i for i in range(dims) if mask & (1 << i)]
        k = len(active)
        system = np.zeros((k + 1, k + 1))
        system[:k, :k] = h[np.ix_(active, active)]
        system[:k, k] = system[k, :k] = 1.0
        solution = np.linalg.solve(system, np.r_[rhs[active], 1.0])[:k]
        if not np.isfinite(solution).all() or np.any(solution < -1e-10):
            continue
        w = np.zeros(dims)
        w[active] = np.maximum(solution, 0.0)
        w /= w.sum()
        value = loss(w)
        if value < best_loss:
            best, best_loss = w, value
    return best


class MetricClusterer:
    """Learn global distance weights, then use the same grouping policy as pref.

    Ratings mean 'how much I want these files in the same group for this purpose'.
    They are soft regression targets, not must-link/cannot-link guarantees.
    """
    name = "metric"

    def __init__(self, cfg: Config):
        if not np.isfinite(cfg.cluster_alpha) or not 0 <= cfg.cluster_alpha <= 1:
            raise ValueError("cluster_alpha must be between 0 and 1")
        if not np.isfinite(cfg.metric_l2) or cfg.metric_l2 <= 0:
            raise ValueError("metric_l2 must be finite and positive")
        self.alpha, self.pct = cfg.cluster_alpha, cfg.cluster_pct
        self.l2, self.use_type = cfg.metric_l2, cfg.metric_use_type
        self.diagnostics: dict = {}

    def distance_matrix(self, record: Record, prefs: Preferences) -> np.ndarray:
        """Fit our distance reweighting model, then apply it to all file pairs.

        See fit_distance_weights() for Bilenko et al. (2004) and the distinction
        between that related work and this project's regression objective.
        Seeding/anchor adaptations are documented in preference_groups().
        """
        features = distance_features(record, self.use_type)
        names = ["content", "folder"] + (["type"] if self.use_type else [])
        alpha = GUIDE_ALPHA.get(prefs.guide.get("group_by", ""), self.alpha)
        prior = np.array([alpha, 1.0 - alpha] + ([0.0] if self.use_type else []))
        pairs, stats = resolve_ratings(record, prefs.pairs)
        idx = record.file_index
        x = np.array([features[idx[p["a"]], idx[p["b"]]] for p in pairs]).reshape(-1, len(names))
        y = np.array([(5.0 - p["score"]) / 4.0 for p in pairs])
        fallback = None
        weights = prior.copy()
        if not pairs:
            fallback = "no_valid_ratings"
        else:
            try:
                weights = fit_distance_weights(x, y, prior, self.l2)
            except (np.linalg.LinAlgError, FloatingPointError):
                log.warning("distance-weight fit failed; using the prior", exc_info=True)
                fallback = "solver_failed"
        before = float(np.mean((x @ prior - y) ** 2)) if pairs else None
        after = float(np.mean((x @ weights - y) ** 2)) if pairs else None
        self.diagnostics = {
            "method": self.name, "rating_meaning": "same_group_preference",
            "weights": dict(zip(names, map(float, weights))),
            "prior": dict(zip(names, map(float, prior))), "metric_l2": self.l2,
            "ratings": stats, "fallback": fallback,
            "train_rmse_before": float(np.sqrt(before)) if pairs else None,
            "train_rmse_after": float(np.sqrt(after)) if pairs else None,
            "objective_before": before,
            "objective_after": after + self.l2 * float(np.sum((weights - prior) ** 2)) if pairs else None,
        }
        log.info("learned distance weights: %s (%d ratings, fallback=%s)",
                 self.diagnostics["weights"], len(pairs), fallback)
        # Preserve the existing float32 calculation exactly when no learning took place.
        if fallback:
            dist = mixed_distance(record, alpha)
        else:
            dist = np.clip(features @ weights, 0.0, 1.0)
            np.fill_diagonal(dist, 0.0)
        self.distances_ = dist
        return dist

    def cluster(self, record: Record, prefs: Preferences) -> list[Group]:
        """Cluster learned distances; literature and local choices are documented above."""
        return preference_groups(record, prefs, self.distance_matrix(record, prefs), self.pct)


def groups_from_indices(record: Record, members: list[list[int]]) -> list[Group]:
    ordered = sorted((sorted(m) for m in members if m), key=lambda m: (-len(m), m[0]))
    return [Group(id=f"g{i + 1}", name="", members=[record.files[j].id for j in m])
            for i, m in enumerate(ordered)]


def groups_from_labels(record: Record, labels: np.ndarray) -> list[Group]:
    members = {}
    for i, label in enumerate(labels):
        if label >= 0:
            members.setdefault(int(label), []).append(i)
    return groups_from_indices(record, list(members.values()))


class _RatedDistanceClusterer(PreferenceClusterer):
    """The new methods share the same validated, guide/rating-adjusted input distance."""

    def distance_matrix(self, record: Record, prefs: Preferences) -> np.ndarray:
        self.ratings_, self.rating_stats_ = resolve_ratings(record, prefs.pairs)
        return super().distance_matrix(record, replace(prefs, pairs=self.ratings_))


class ConstrainedClusterer(_RatedDistanceClusterer):
    """Custom constrained average linkage, not a reproduction of COP-KMeans.

    Scores 4-5 are must-links, 1-2 are cannot-links. Distinct anchors are also
    cannot-links. For inconsistent input, cannot-links take priority; conflicting
    must-links are skipped in descending score/canonical file-ID order and reported.
    """
    name = "constrained"

    def cluster(self, record: Record, prefs: Preferences) -> list[Group]:
        """Merge compatible groups with instance-level constraints.

        Related reference: I. Davidson and S. S. Ravi (2009), "Using instance-level
        constraints in agglomerative hierarchical clustering: theoretical and
        empirical results", Data Mining and Knowledge Discovery 18, 257-282.
        https://doi.org/10.1007/s10618-008-0103-4

        This is our constrained average-linkage variant, not a paper reproduction.
        The 4-5/1-2 rating cutoffs, distinct-anchor constraints, cannot-link priority
        and deterministic handling of contradictory must-links are project policies.
        The average-linkage foundation is cited in agglomerate().
        """
        dist = self.distance_matrix(record, prefs)
        n, idx = len(record.files), record.file_index
        forbidden = {i: set() for i in range(n)}
        negatives = [(idx[p["a"]], idx[p["b"]]) for p in self.ratings_ if p["score"] <= 2]
        anchors = list(dict.fromkeys(idx[a] for a in map(record.resolve, prefs.anchors) if a))
        negatives += [(a, b) for i, a in enumerate(anchors) for b in anchors[i + 1:]]
        for a, b in negatives:
            forbidden[a].add(b)
            forbidden[b].add(a)
        clusters = {i: {i} for i in range(n)}
        owner = {i: i for i in range(n)}
        skipped = []

        def allowed(a, b):
            return not forbidden[a].intersection(clusters[b])

        def join(a, b, new):
            members = clusters.pop(a) | clusters.pop(b)
            blocked = forbidden.pop(a) | forbidden.pop(b)
            clusters[new], forbidden[new] = members, blocked
            for member in members:
                owner[member] = new

        positives = sorted((p for p in self.ratings_ if p["score"] >= 4),
                           key=lambda p: (-p["score"], p["a"], p["b"]))
        next_id = n
        for p in positives:
            a, b = owner[idx[p["a"]]], owner[idx[p["b"]]]
            if a == b:
                continue
            if not allowed(a, b):
                skipped.append({**p, "reason": "cannot_link_or_distinct_anchors"})
                continue
            join(a, b, next_id)
            next_id += 1

        threshold = float(np.percentile(upper(dist), self.pct)) if n >= 2 else 0.0
        distances, queue = {}, []

        def key(a, b):
            return tuple(sorted((a, b)))

        ids = list(clusters)
        for pos, a in enumerate(ids):
            for b in ids[pos + 1:]:
                value = float(dist[np.ix_(sorted(clusters[a]), sorted(clusters[b]))].mean())
                distances[key(a, b)] = value
                heapq.heappush(queue, (value, a, b))
        while queue:
            value, a, b = heapq.heappop(queue)
            if value >= threshold:
                break
            if a not in clusters or b not in clusters or not allowed(a, b):
                continue
            size_a, size_b = len(clusters[a]), len(clusters[b])
            updates = {c: (size_a * distances[key(a, c)] + size_b * distances[key(b, c)]) / (size_a + size_b)
                       for c in clusters if c not in (a, b)}
            join(a, b, next_id)
            for c, updated in updates.items():
                distances[key(c, next_id)] = updated
                heapq.heappush(queue, (updated, c, next_id))
            next_id += 1
        if skipped:
            log.warning("constrained clustering skipped %d conflicting must-links", len(skipped))
        self.diagnostics = {"method": self.name, "ratings": self.rating_stats_,
                            "must_links": len(positives), "cannot_links": len({tuple(sorted(p)) for p in negatives}),
                            "skipped_must_links": skipped, "merge_threshold": threshold,
                            "anchor_policy": "distinct_anchors_are_cannot_links"}
        return groups_from_indices(record, [list(m) for m in clusters.values()])


def graph_components(affinity: np.ndarray) -> list[list[int]]:
    remaining, components = set(range(len(affinity))), []
    while remaining:
        start = min(remaining)
        remaining.remove(start)
        members, pending = [start], [start]
        while pending:
            node = pending.pop()
            neighbours = sorted(remaining.intersection(np.flatnonzero(affinity[node] > 0)))
            remaining.difference_update(neighbours)
            members.extend(neighbours)
            pending.extend(neighbours)
        components.append(sorted(members))
    return components


class GraphClusterer(_RatedDistanceClusterer):
    """Spectral clustering of kNN semantic affinities plus raw imports/links.

    Group count is selected by the normalized-Laplacian eigengap, without test
    labels. Anchors are not enforced; ratings bias affinities but are soft here.
    """
    name = "graph"

    def __init__(self, cfg: Config):
        super().__init__(cfg)
        if cfg.graph_neighbors < 1 or cfg.graph_max_clusters < 2:
            raise ValueError("graph_neighbors must be >=1 and graph_max_clusters >=2")
        if not np.isfinite(cfg.graph_reference_weight) or cfg.graph_reference_weight < 0:
            raise ValueError("graph_reference_weight must be finite and nonnegative")
        self.neighbors, self.max_clusters = cfg.graph_neighbors, cfg.graph_max_clusters
        self.reference_weight, self.seed = cfg.graph_reference_weight, cfg.cluster_seed

    def cluster(self, record: Record, prefs: Preferences) -> list[Group]:
        """Build and partition a hybrid semantic/reference graph.

        Spectral foundation (similarity graphs, normalized Laplacians, eigengap):
        U. von Luxburg (2007), "A Tutorial on Spectral Clustering".
        https://arxiv.org/abs/0711.0189
        QR label assignment used by sklearn's assign_labels="cluster_qr":
        A. Damle, V. Minden, L. Ying (2019), "Simple, direct and efficient multi-way
        spectral clustering". https://doi.org/10.1093/imaiai/iay008

        Software-structure motivation: S. Mancoridis et al. (IWPC 1998), "Using
        Automatic Clustering to Produce High-Level System Organizations of Source
        Code". https://doi.org/10.1109/WPC.1998.693283
        The software-modularization algorithms in that work are not reproduced here.

        Adding imports/links to a semantic kNN graph, median-positive-distance
        bandwidth, rating-edge edits and the group-count bounds are our adaptations
        for mixed project files, not a published guarantee of onboarding usefulness.
        """
        from sklearn.cluster import SpectralClustering
        from ..srcs.candidates import reference_candidates

        dist = self.distance_matrix(record, prefs)
        n, idx = len(record.files), record.file_index
        positives = upper(dist)
        sigma = max(float(np.median(positives[positives > 0])) if np.any(positives > 0) else 1.0, 1e-8)
        affinity = np.zeros((n, n))
        for i in range(n):
            neighbours = [j for j in np.argsort(dist[i], kind="stable") if j != i][:self.neighbors]
            affinity[i, neighbours] = np.exp(-dist[i, neighbours] ** 2 / (2 * sigma ** 2))
        affinity = np.maximum(affinity, affinity.T)
        references = {tuple(sorted((idx[a], idx[b]))) for a, b, reason, _, _ in reference_candidates(record)
                      if reason in ("imports", "links_to")}
        for a, b in references:
            affinity[a, b] += self.reference_weight
            affinity[b, a] += self.reference_weight
        for p in self.ratings_:
            a, b = idx[p["a"]], idx[p["b"]]
            if p["score"] <= 2:
                affinity[a, b] = affinity[b, a] = 0.0
            elif p["score"] >= 4:
                affinity[a, b] += 1.0
                affinity[b, a] += 1.0
        np.fill_diagonal(affinity, 0.0)
        self.affinity_ = affinity
        components = graph_components(affinity)
        spectrum, chosen, gap = [], len(components), None
        # Keep disconnected components separate instead of applying an ambiguous
        # spectral embedding across disconnected pieces (including isolated files).
        if n > 2 and len(components) == 1:
            inverse = 1.0 / np.sqrt(np.maximum(affinity.sum(1), 1e-12))
            laplacian = np.eye(n) - inverse[:, None] * affinity * inverse[None, :]
            spectrum = np.linalg.eigvalsh(laplacian).tolist()
            candidates = range(max(2, len(components)), min(self.max_clusters, n - 1) + 1)
            chosen = max(candidates, key=lambda k: (spectrum[k] - spectrum[k - 1], -k))
            gap = spectrum[chosen] - spectrum[chosen - 1]
        if chosen <= len(components):
            groups = groups_from_indices(record, components)
        else:
            labels = SpectralClustering(n_clusters=chosen, affinity="precomputed", assign_labels="cluster_qr",
                                        random_state=self.seed).fit_predict(affinity)
            groups = groups_from_labels(record, labels)
        self.diagnostics = {"method": self.name, "ratings": self.rating_stats_, "neighbors": self.neighbors,
                            "reference_weight": self.reference_weight, "structural_pairs": len(references),
                            "components": len(components), "selected_clusters": chosen,
                            "eigengap": gap, "eigenvalues": spectrum, "seed": self.seed,
                            "anchor_policy": "not_enforced", "pair_policy": "soft_affinity_bias"}
        return groups


class HdbscanClusterer(_RatedDistanceClusterer):
    """Density groups on the shared input distance; noise remains ungrouped."""
    name = "hdbscan"

    def __init__(self, cfg: Config):
        super().__init__(cfg)
        if cfg.hdbscan_min_cluster_size < 2 or cfg.hdbscan_min_samples < 1:
            raise ValueError("HDBSCAN requires min_cluster_size >=2 and min_samples >=1")
        self.min_size, self.min_samples = cfg.hdbscan_min_cluster_size, cfg.hdbscan_min_samples

    def cluster(self, record: Record, prefs: Preferences) -> list[Group]:
        """Use standard HDBSCAN and leave noise files ungrouped.

        Reference: R. J. G. B. Campello, D. Moulavi, A. Zimek, J. Sander (2015),
        "Hierarchical Density Estimates for Data Clustering, Visualization, and
        Outlier Detection", ACM TKDD 10(1), Article 5.
        https://doi.org/10.1145/2733381
        Implementation and min_samples semantics (including the point itself):
        https://scikit-learn.org/stable/modules/generated/sklearn.cluster.HDBSCAN.html

        HDBSCAN itself comes from sklearn; the guide/rating-adjusted input distance
        and default min_cluster_size=2/min_samples=2 are local experiment choices.
        """
        from sklearn.cluster import HDBSCAN

        dist = self.distance_matrix(record, prefs)
        n = len(record.files)
        if n < max(self.min_size, self.min_samples):
            labels = np.full(n, -1)
        else:
            labels = HDBSCAN(min_cluster_size=self.min_size, min_samples=self.min_samples,
                             metric="precomputed", copy=True).fit_predict(dist.astype(float))
        self.diagnostics = {"method": self.name, "ratings": self.rating_stats_,
                            "min_cluster_size": self.min_size, "min_samples": self.min_samples,
                            "noise_files": [record.files[i].path for i, label in enumerate(labels) if label < 0],
                            "anchor_policy": "not_enforced", "pair_policy": "distance_bias"}
        return groups_from_labels(record, labels)


# ---- registry ------------------------------------------------------------------------------------
CLUSTERERS = {"baseline": BaselineClusterer, "pref": PreferenceClusterer, "metric": MetricClusterer,
              "constrained": ConstrainedClusterer, "graph": GraphClusterer, "hdbscan": HdbscanClusterer}


def get_clusterer(name: str, cfg: Config) -> Clusterer:
    return load_component(name, CLUSTERERS, cfg)
