"""Estimate file importance from visible links. Explicit level choices take precedence."""
from __future__ import annotations

import numpy as np

from ..schema import DIRECTED_RELATIONS, LEVELS, VISIBLE_STATUS, Graph


def assign_levels(graph: Graph) -> None:
    count = len(graph.nodes)
    if not count:
        return
    index = {node.id: i for i, node in enumerate(graph.nodes)}
    sources, targets = [], []
    for edge in graph.edges:
        if edge.status not in VISIBLE_STATUS:
            continue
        a, b = index[edge.source], index[edge.target]
        sources.append(a)
        targets.append(b)
        if not edge.user_directed and edge.relation not in DIRECTED_RELATIONS:
            sources.append(b)
            targets.append(a)

    src, dst = np.asarray(sources, dtype=int), np.asarray(targets, dtype=int)
    degree = np.bincount(src, minlength=count)
    scores = np.full(count, 1.0 / count)
    for _ in range(200):
        incoming = np.bincount(dst, weights=scores[src] / degree[src], minlength=count)
        updated = 0.15 / count + 0.85 * (incoming + scores[degree == 0].sum() / count)
        delta = np.abs(updated - scores).sum()
        scores = updated
        if delta < 1e-12:
            break

    # Give tied files the same tier, including all-middle when no evidence separates them.
    rounded = scores.round(12).tolist()
    distinct = sorted(set(rounded))
    tiers = {}
    for rank, score in enumerate(distinct):
        percentile = (rank + 0.5) / len(distinct)
        tiers[score] = LEVELS[int(3 * percentile)]
    for node, score in zip(graph.nodes, rounded):
        node.pagerank = score
        if not node.manual_level:
            node.level = tiers[score]


def final_graph_from_dict(data: dict) -> Graph:
    graph = Graph.from_dict(data)
    if any(not node.level for node in graph.nodes):
        assign_levels(graph)
    return graph
