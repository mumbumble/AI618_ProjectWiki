from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from projectwiki.config import Config
from projectwiki.models.preference import get_corrector
from projectwiki.schema import Edge, FeedbackEvent, Graph, Node, edge_key
from projectwiki.srcs.finalize import finalize


@pytest.mark.parametrize(("similarity", "expected_scale"), [(0.5, 2.0), (0.82, 1.0), (0.90, 0.5)])
def test_best_of_n_selects_by_preference_and_preserves_edits(similarity, expected_scale):
    nodes = [Node(id=name, path=name, type="text", title=name, group=None) for name in "abcd"]
    edges = [Edge(id=edge_key(a, b), source=a, target=b, relation="mentions", reason="mentions",
                  direct=False, score=0.5) for a, b in (("a", "b"), ("c", "d"))]
    graph = Graph(nodes=nodes, edges=edges, groups=[])
    vector = [similarity, np.sqrt(1 - similarity ** 2)]
    record = SimpleNamespace(file_index={node.id: i for i, node in enumerate(nodes)},
                             file_emb=np.array([[1, 0], [1, 0], vector, vector]))
    feedback = [FeedbackEvent(type="edge_confirm", source="a", target="b"),
                FeedbackEvent(type="edge_irrelevant", source="a", target="b"),
                FeedbackEvent(type="node_move", node="a", group="Notes")]
    cfg = Config(corrector="best-of-n")
    correction = get_corrector(cfg.corrector, cfg).correct(graph, feedback, record)
    result = correction.selection
    assert result["scale"] == expected_scale
    assert (result["approvals"], result["rejections"], result["scored_edges"]) == (0, 1, 1)
    assert len(result["candidates"]) == 3
    for row in result["candidates"]:
        scale = row["scale"]
        candidate_cfg = replace(cfg, drift_gain=cfg.drift_gain * scale, drift_tau=cfg.drift_tau * scale)
        drift = get_corrector("drift", candidate_cfg).correct(graph, feedback, record)
        candidate = finalize(graph, drift, feedback, candidate_cfg)
        direct, untouched = candidate.edges
        assert direct.status == "removed_irrelevant"
        assert candidate.groups[0].members == ["a"]
        actual = 0 if untouched.status == "removed_by_corrector" else max(0, min(1, untouched.score))
        assert row["score"] == pytest.approx(100 * (1 - (actual - 1 / 3) ** 2))
        if scale == expected_scale:
            assert finalize(graph, correction, feedback, cfg) == candidate

    # When every edge is explicitly judged, there is no comparison score.
    feedback.append(FeedbackEvent(type="edge_confirm", source="c", target="d"))
    tie = get_corrector(cfg.corrector, cfg).correct(graph, feedback, record).selection
    assert tie["scale"] == min(cfg.best_of_n_scales)
    assert all(row["score"] is None for row in tie["candidates"])
