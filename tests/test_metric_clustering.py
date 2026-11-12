import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from projectwiki.config import Config
from projectwiki.models import clustering
from projectwiki.models.clustering import (
    MetricClusterer, distance_features, fit_distance_weights, get_clusterer, mixed_distance, resolve_ratings,
)
from projectwiki.schema import FileRecord, Preferences
from projectwiki.srcs.cluster_eval import compare_clusterers
from projectwiki.srcs.record import Record


@pytest.fixture
def record():
    # Each folder contains unrelated roles; the same roles recur in other folders.
    paths = ["a/train.py", "a/notes.md", "b/train.py", "b/notes.md", "c/train.py", "c/notes.md"]
    files = [FileRecord(id=f"f{i}", path=p, type="python" if p.endswith(".py") else "markdown",
                        sha256="test", size=1, title=p) for i, p in enumerate(paths)]
    vectors = np.tile(np.eye(2, dtype=np.float32), (3, 1))
    return Record("synthetic", files, [], np.empty((0, 2)), vectors, "synthetic")


def training_prefs():
    return Preferences(pairs=[{"a": "a/train.py", "b": "b/train.py", "score": 5},
                              {"a": "a/train.py", "b": "a/notes.md", "score": 1}])


def test_learned_distance_generalizes_and_preserves_inputs(record):
    original = record.file_emb.copy()
    prefs = training_prefs()
    before = mixed_distance(record, 0.6)
    model = get_clusterer("metric", Config())
    after = model.distance_matrix(record, prefs)
    # Neither of these pairs was rated: the new distance transfers to other files.
    assert after[2, 4] < before[2, 4]  # same role, different folders
    assert after[2, 3] > before[2, 3]  # different roles, same folder
    weights = list(model.diagnostics["weights"].values())
    assert min(weights) >= 0 and sum(weights) == pytest.approx(1.0)
    assert model.diagnostics["train_rmse_after"] < model.diagnostics["train_rmse_before"]
    assert model.diagnostics["objective_after"] <= model.diagnostics["objective_before"]
    assert 0 < after[0, 2] < 1  # learned target is not overwritten with the user's 0/1 distance
    np.testing.assert_array_equal(record.file_emb, original)
    np.testing.assert_allclose(after, after.T)
    np.testing.assert_array_equal(np.diag(after), np.zeros(6))
    assert np.isfinite(after).all() and after.min() >= 0 and after.max() <= 1
    np.testing.assert_array_equal(model.distance_matrix(record, prefs), after)
    groups = model.cluster(record, prefs)
    members = [fid for g in groups for fid in g.members]
    assert sorted(members) == sorted(record.file_by_id) and len(set(members)) == 6
    assert prefs.pairs == training_prefs().pairs


@pytest.mark.parametrize("guide", [{}, {"group_by": "content"}, {"group_by": "folder"}])
def test_no_ratings_matches_pref_including_anchors(record, guide):
    prefs = Preferences(guide=guide, anchors=["a/train.py", "a/notes.md"])
    cfg = Config()
    pref = get_clusterer("pref", cfg)
    metric = MetricClusterer(cfg)
    np.testing.assert_array_equal(metric.distance_matrix(record, prefs), pref.distance_matrix(record, prefs))
    assert metric.cluster(record, prefs) == pref.cluster(record, prefs)
    assert metric.diagnostics["fallback"] == "no_valid_ratings"
    assert metric.diagnostics["train_rmse_after"] is None


def test_pref_anchor_policy_regression(record):
    prefs = Preferences(anchors=["a/train.py", "a/notes.md"], pairs=training_prefs().pairs[:1])
    groups = get_clusterer("pref", Config()).cluster(record, prefs)
    assert [set(g.members) for g in groups] == [{"f0", "f2", "f4"}, {"f1", "f3", "f5"}]


def test_invalid_and_reversed_duplicate_ratings(record, caplog):
    pairs = [None, {"a": "missing", "b": "f1", "score": 5},
             {"a": "f0", "b": "a/train.py", "score": 5}]
    pairs += [{"a": "f0", "b": "f1", "score": v} for v in (None, "bad", True, -1, 6, float("nan"), float("inf"))]
    pairs += [{"a": "a/train.py", "b": "b/train.py", "score": 5},
              {"a": "f2", "b": "f0", "score": 1}]
    valid, stats = resolve_ratings(record, pairs)
    assert valid == [{"a": "f0", "b": "f2", "score": 1.0}]
    assert stats == {"received": 12, "valid": 1, "invalid": 10, "duplicates": 1}
    assert "skipping grouping rating" in caplog.text
    model = MetricClusterer(Config())
    np.testing.assert_array_equal(model.distance_matrix(record, Preferences(pairs=pairs[:10])),
                                  mixed_distance(record, 0.6))


def test_simplex_solver_and_regularization():
    x = np.array([[0.1, 0.9, 0], [0.9, 0.1, 1], [0.2, 0.7, 0]])
    y, prior = np.array([0, 1, 0.25]), np.array([0.6, 0.4, 0])
    weights = fit_distance_weights(x, y, prior, 0.1)

    def objective(w):
        return np.mean((x @ w - y) ** 2) + 0.1 * np.sum((w - prior) ** 2)

    # Compare to feasible alternatives, independent of the face-enumeration solver.
    alternatives = np.random.default_rng(7).dirichlet(np.ones(3), size=500)
    assert all(objective(weights) <= objective(w) + 1e-12 for w in alternatives)
    strong = fit_distance_weights(x, y, prior, 100)
    assert np.linalg.norm(strong - prior) < np.linalg.norm(weights - prior)


def test_type_channel_can_be_disabled(record):
    model = MetricClusterer(Config(metric_use_type=False))
    dist = model.distance_matrix(record, training_prefs())
    assert set(model.diagnostics["weights"]) == {"content", "folder"}
    assert distance_features(record, False).shape == (6, 6, 2)
    assert np.isfinite(dist).all()


def test_solver_failure_uses_prior(record, monkeypatch):
    def fail(*args):
        raise np.linalg.LinAlgError("unavailable")

    monkeypatch.setattr(clustering, "fit_distance_weights", fail)
    model = MetricClusterer(Config())
    np.testing.assert_array_equal(model.distance_matrix(record, training_prefs()), mixed_distance(record, 0.6))
    assert model.diagnostics["fallback"] == "solver_failed"


@pytest.mark.parametrize("size", [0, 1, 2])
def test_small_projects(record, size):
    small = Record(record.root, record.files[:size], [], np.empty((0, 2)), record.file_emb[:size], "synthetic")
    model = MetricClusterer(Config())
    assert [fid for g in model.cluster(small, Preferences()) for fid in g.members] == [f.id for f in small.files]


@pytest.mark.parametrize("l2", [0, -1, float("nan"), float("inf")])
def test_invalid_regularization_is_rejected(l2):
    with pytest.raises(ValueError, match="metric_l2"):
        MetricClusterer(Config(metric_l2=l2))


def test_evaluation_uses_held_out_ratings_only(record):
    prefs = training_prefs()
    test = [{"a": "b/train.py", "b": "c/train.py", "score": 5},
            {"a": "b/train.py", "b": "b/notes.md", "score": 1}]
    validation = [{"a": "a/notes.md", "b": "b/notes.md", "score": 5},
                  {"a": "a/notes.md", "b": "c/train.py", "score": 1}]
    cfg = Config()
    result = compare_clusterers(record, prefs, test, cfg, validation, [0.01, 1.0])
    changed_test = [{**p, "score": 6 - p["score"]} for p in test]
    other = compare_clusterers(record, prefs, changed_test, cfg, validation, [0.01, 1.0])
    assert result["selection"] == other["selection"]
    assert result["methods"]["metric"]["diagnostics"] == other["methods"]["metric"]["diagnostics"]
    assert cfg.metric_l2 == 0.1  # model selection does not modify the caller's Config
    assert set(result["methods"]) == {"baseline", "pref", "metric"}
    assert result["splits"]["test"]["valid"] == 2
    assert result["methods"]["metric"]["distance_rmse"] < result["methods"]["pref"]["distance_rmse"]
    assert result["methods"]["metric"]["balanced_accuracy"] is not None
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("split", ["train_test", "train_validation", "validation_test"])
def test_evaluation_rejects_overlap_including_aliases(record, split):
    train = training_prefs()
    test = [{"a": "f2", "b": "f4", "score": 5}]
    validation = [{"a": "f1", "b": "f3", "score": 5}]
    if split == "train_test":
        test = [{"a": "f2", "b": "f0", "score": 1}]
    elif split == "train_validation":
        validation = [{"a": "f2", "b": "f0", "score": 1}]
    else:
        validation = [{"a": "f4", "b": "f2", "score": 1}]
    with pytest.raises(ValueError, match="overlap"):
        compare_clusterers(record, train, test, Config(), validation)


def test_evaluation_requires_valid_test_and_separate_validation(record):
    with pytest.raises(ValueError, match="at least one"):
        compare_clusterers(record, training_prefs(), [], Config())
    with pytest.raises(ValueError, match="separate validation"):
        compare_clusterers(record, training_prefs(), [{"a": "f2", "b": "f4", "score": 5}],
                           Config(), l2_grid=[0.1])


def test_evaluation_script_preserves_saved_build(record, tmp_path):
    record.save(tmp_path)
    Config().save(tmp_path / "config.json")
    prefs_path = tmp_path / "prefs.json"
    prefs_path.write_text(json.dumps({"pairs": training_prefs().pairs}), encoding="utf-8")
    test_path = tmp_path / "test.json"
    test_path.write_text(json.dumps([{"a": "f2", "b": "f4", "score": 5}]), encoding="utf-8")
    graph_path = tmp_path / "graph.json"
    graph_path.write_text("saved graph", encoding="utf-8")
    snapshot = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    command = [sys.executable, "-B", "scripts/evaluate_clustering.py", str(tmp_path), "--test", str(test_path)]
    result = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "metric" in result.stdout
    assert set(json.loads((tmp_path / "clustering_eval.json").read_text(encoding="utf-8"))["methods"]) == {
        "baseline", "pref", "metric"}
    assert all(p.read_bytes() == content for p, content in snapshot.items())
    for protected in (graph_path, tmp_path / "view.html", tmp_path / "record" / "new.json"):
        rejected = subprocess.run(command + ["-o", str(protected)], cwd=Path(__file__).resolve().parents[1],
                                  capture_output=True, text=True)
        assert rejected.returncode != 0 and "overwrite" in rejected.stderr
    assert graph_path.read_text(encoding="utf-8") == "saved graph"
