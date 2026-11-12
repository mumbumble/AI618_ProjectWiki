import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from projectwiki.config import Config
from projectwiki.models.clustering import get_clusterer
from projectwiki.schema import Chunk, FileRecord, Group, Preferences, Ref
from projectwiki.srcs.cluster_eval import compare_clusterers, describe_groups, grouping_scores, resolve_tasks, task_scores
from projectwiki.srcs.record import Record


@pytest.fixture
def record():
    paths = ["a/one.py", "a/two.py", "a/three.py", "b/four.py", "b/five.py", "b/six.py"]
    vectors = np.array([[1, 0], [1, .01], [1, -.01], [0, 1], [.01, 1], [-.01, 1]], dtype=np.float32)
    vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
    files = [FileRecord(f"f{i}", path, "python", "test", 1, path) for i, path in enumerate(paths)]
    chunk = Chunk("f0#0", "f0", "module", "module", "from b.four import Model\n<script>alert(1)</script>")
    files[0].chunk_ids = [chunk.id]
    files[0].refs = [Ref("import", "b.four", chunk.id)]
    return Record("synthetic", files, [chunk], np.array([[1, 0]], dtype=np.float32), vectors, "synthetic")


def group_map(groups):
    return {fid: group.id for group in groups for fid in group.members}


def test_constraints_transfer_through_components_and_block_merges(record):
    prefs = Preferences(anchors=["f0", "f4"], pairs=[
        {"a": "f0", "b": "f1", "score": 5},
        {"a": "f1", "b": "f3", "score": 4},
        {"a": "f0", "b": "f2", "score": 1},
    ])
    model = get_clusterer("constrained", Config())
    groups = model.cluster(record, prefs)
    assigned = group_map(groups)
    assert assigned["f0"] == assigned["f1"] == assigned["f3"]
    assert assigned["f0"] != assigned["f2"] and assigned["f0"] != assigned["f4"]
    assert model.diagnostics["skipped_must_links"] == []
    assert sorted(assigned) == sorted(record.file_by_id)
    assert sum(len(g.members) for g in groups) == 6


def test_inconsistent_constraints_are_reported_and_cannot_links_win(record, caplog):
    prefs = Preferences(pairs=[{"a": "f0", "b": "f1", "score": 5},
                               {"a": "f1", "b": "f2", "score": 4},
                               {"a": "f0", "b": "f2", "score": 1}])
    model = get_clusterer("constrained", Config())
    assigned = group_map(model.cluster(record, prefs))
    assert assigned["f0"] == assigned["f1"] != assigned["f2"]
    assert len(model.diagnostics["skipped_must_links"]) == 1
    assert "conflicting must-links" in caplog.text
    anchors = Preferences(anchors=["f0", "f1"], pairs=prefs.pairs[:1])
    assigned = group_map(model.cluster(record, anchors))
    assert assigned["f0"] != assigned["f1"]
    assert len(model.diagnostics["skipped_must_links"]) == 1


def test_graph_uses_raw_imports_and_ratings_without_editing_embeddings(record):
    before = record.file_emb.copy()
    cfg = Config(graph_neighbors=1)
    graph = get_clusterer("graph", cfg)
    groups = graph.cluster(record, Preferences())
    assert graph.affinity_[0, 3] >= cfg.graph_reference_weight
    assert graph.diagnostics["structural_pairs"] == 1
    np.testing.assert_allclose(graph.affinity_, graph.affinity_.T)
    np.testing.assert_array_equal(record.file_emb, before)
    assert groups == graph.cluster(record, Preferences())
    graph.cluster(record, Preferences(pairs=[{"a": "f0", "b": "f3", "score": 1}]))
    assert graph.affinity_[0, 3] == graph.affinity_[3, 0] == 0


def test_graph_keeps_disconnected_components_separate(record):
    # With no cross-cluster imports or rating edges, a 1-NN graph has two components.
    record.files[0].refs = []
    graph = get_clusterer("graph", Config(graph_neighbors=1))
    groups = graph.cluster(record, Preferences())
    assert {frozenset(g.members) for g in groups} == {frozenset(("f0", "f1", "f2")), frozenset(("f3", "f4", "f5"))}
    assert graph.diagnostics["components"] == 2


def test_hdbscan_finds_dense_cores_without_mutating_vectors(record):
    before = record.file_emb.copy()
    groups = get_clusterer("hdbscan", Config()).cluster(record, Preferences())
    assigned = group_map(groups)
    assert assigned["f0"] == assigned["f1"] == assigned["f2"]
    assert assigned["f3"] == assigned["f4"] == assigned["f5"]
    assert assigned["f0"] != assigned["f3"]
    np.testing.assert_array_equal(record.file_emb, before)


def test_noise_is_abstention_and_counts_as_individual_exploration(record):
    cfg = Config(hdbscan_min_cluster_size=10)
    pairs = [{"a": "f0", "b": "f1", "score": 5}, {"a": "f0", "b": "f3", "score": 1}]
    tasks = [{"name": "find implementation", "files": ["f0", "f1"]}]
    result = compare_clusterers(record, Preferences(), pairs, cfg, methods=["hdbscan"], tasks=tasks)
    density = result["methods"]["hdbscan"]
    assert density["group_count"] == 0 and density["ungrouped"] == 6
    assert density["pair_accuracy"] == 0 and density["pair_coverage"] == 0
    assert density["abstained_pairs"] == 2 and density["covered_pair_accuracy"] is None
    assert density["task_scores"][0]["groups_to_visit"] == 2
    assert density["task_scores"][0]["files_to_scan"] == 2
    assert {p["predicted"] for p in density["pair_outcomes"]} == {"abstained"}


def test_onboarding_proxy_exposes_fragmentation_and_broad_groups(record):
    tasks = resolve_tasks(record, [{"name": "read implementation", "files": ["f0", "f1"]}])
    broad = task_scores([Group("all", "", list(record.file_by_id))], tasks, record)[0]
    split = task_scores([Group("first", "", ["f0"]), Group("second", "", ["f1"])], tasks, record)[0]
    assert broad["groups_to_visit"] == 1 and broad["files_to_scan"] == 6
    assert split["groups_to_visit"] == 2 and split["files_to_scan"] == 2
    # Missing either endpoint cannot be counted as a correct separation.
    score = grouping_scores([Group("first", "", ["f0"])], [{"a": "f0", "b": "f3", "score": 1}])
    assert score["pair_accuracy"] == 0 and score["abstained_pairs"] == 1


@pytest.mark.parametrize("name", ["constrained", "graph", "hdbscan"])
@pytest.mark.parametrize("size", [0, 1, 2])
def test_new_methods_handle_tiny_projects(record, name, size):
    files = record.files[:size]
    for file in files:
        file.refs = []
    tiny = Record(record.root, files, record.chunks, record.chunk_emb, record.file_emb[:size], record.encoder_id)
    groups = get_clusterer(name, Config()).cluster(tiny, Preferences())
    members = [fid for g in groups for fid in g.members]
    assert len(members) == len(set(members)) and set(members) <= set(tiny.file_by_id)


def test_report_and_cli_compare_all_six_on_one_saved_record(record, tmp_path):
    record.save(tmp_path)
    Config().save(tmp_path / "config.json")
    (tmp_path / "prefs.json").write_text(json.dumps({"pairs": [{"a": "f0", "b": "f1", "score": 5}]}), encoding="utf-8")
    test = tmp_path / "test.json"
    test.write_text(json.dumps([{"a": "f3", "b": "f4", "score": 5},
                                {"a": "f0", "b": "f5", "score": 1}]), encoding="utf-8")
    tasks = tmp_path / "tasks.json"
    tasks.write_text(json.dumps([{"name": "read implementation", "files": ["f0", "f1"]}]), encoding="utf-8")
    report = tmp_path / "comparison.html"
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    names = ["baseline", "pref", "metric", "constrained", "graph", "hdbscan"]
    command = [sys.executable, "-B", "scripts/evaluate_clustering.py", str(tmp_path), "--test", str(test),
               "--methods", *names, "--tasks", str(tasks), "--html", str(report), "--sensitivity"]
    run = subprocess.run(command, cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    result = json.loads((tmp_path / "clustering_eval.json").read_text(encoding="utf-8"))
    assert list(result["methods"]) == names
    assert result["methods"]["constrained"]["diagnostics"]["method"] == "constrained"
    assert len(result["sensitivity"]) == 9
    assert sum(row["main_setting"] for row in result["sensitivity"]) == 3
    page = report.read_text(encoding="utf-8")
    assert all(name in page for name in names) and "read implementation" in page
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert all(p.read_bytes() == content for p, content in before.items())


def test_checklists_never_change_cluster_training(record, tmp_path):
    prefs = Preferences(pairs=[{"a": "f0", "b": "f1", "score": 5}])
    test = [{"a": "f3", "b": "f4", "score": 5}]
    plain = compare_clusterers(record, prefs, test, Config(), methods=["metric"])
    tasks = [{"name": "different checklist", "files": ["f0", "f4", "f5"]}]
    with_tasks = compare_clusterers(record, prefs, test, Config(), methods=["metric"], tasks=tasks)
    assert plain["methods"]["metric"]["diagnostics"] == with_tasks["methods"]["metric"]["diagnostics"]
    assert plain["methods"]["metric"]["groups"] == with_tasks["methods"]["metric"]["groups"]


def test_missing_task_files_are_rejected(record):
    with pytest.raises(ValueError, match="missing file"):
        resolve_tasks(record, [{"name": "unknown", "files": ["missing.py"]}])


def test_representative_preview_prefers_body_over_a_bare_heading(record):
    heading = Chunk("f0#heading", "f0", "section", "Title", "# Title")
    record.chunk_by_id[heading.id] = heading
    record.files[0].chunk_ids.insert(0, heading.id)
    description = describe_groups([Group("g1", "", ["f0"])], record)[0]
    assert description["preview"].startswith("from b.four")
    assert description["locator"] == "module"
