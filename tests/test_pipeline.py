import json
from itertools import combinations
from types import SimpleNamespace

import pymupdf
import pytest

from projectwiki import pipeline
from projectwiki.config import Config
from projectwiki.models.clustering import get_clusterer
from projectwiki.models.visualization import export_obsidian
from projectwiki.schema import Edge, FeedbackEvent, Graph, Node, Preferences, edge_key
from projectwiki.srcs.candidates import reference_candidates
from projectwiki.srcs.feedback import resolve, validate_events
from projectwiki.srcs.feedback_changes import feedback_changes
from projectwiki.srcs.ingest import ingest
from projectwiki.srcs.levels import assign_levels, final_graph_from_dict
from projectwiki.srcs.initial_preferences import pair_feedback, preferences_from_answers, similar_file_pairs
from projectwiki.srcs.record import Record

from projectwiki.srcs.wiki_approval import StaleGraphError, approve_wiki


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    files = {
        "README.md": "# Demo\nSee [training](src/train.py) and [[notes]]. Data loading lives in data_utils.py.\n",
        "notes.md": "# Notes\nLip-sync loss weight should be 1.0. Results go to results.csv.\n",
        "src/model.py": '"""Model."""\nimport torch\n\nclass Net:\n    def forward(self, x):\n        return x\n',
        "src/train.py": "from .model import Net\nimport data_utils\n\ndef main():\n    Net().forward(1)\n",
        "src/__init__.py": "",
        "data_utils.py": "def load():\n    return []\n",
        "results.csv": "setting,lve\nbase,4.1\n",
        "Makefile": "train:\n\tpython src/train.py\n",
    }
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Paper draft. Training uses src/train.py and the lip-sync loss.")
    doc.save(root / "paper.pdf")
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 8, 8), 0)
    pix.clear_with(255)
    pix.save(root / "fig.png")
    (root / "src" / "model.py:Zone.Identifier").write_text("[ZoneTransfer]")
    return root


class FakeClaude:
    """Answers each structured-output request with a fixed valid object."""

    def __init__(self):
        self.calls = 0
        self.messages = self

    def create(self, **kw):
        self.calls += 1
        props = kw["output_config"]["format"]["schema"]["properties"]
        if "relation" in props:
            ans = {"keep": True, "relation": "uses", "direction": "a_to_b", "label": "테스트 관계",
                   "direct": False, "quote_a": "", "quote_b": ""}
        elif "summary" in props:
            ans = {"summary": "요약", "role": "역할"}
        elif "description" in props and "role" in props:
            ans = {"description": "작은 그림", "role": "plot"}
        else:
            ans = {"name": "그룹", "description": "설명"}
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=json.dumps(ans))],
                               usage=SimpleNamespace(input_tokens=10, output_tokens=5))


def make_cfg(**kw):
    return Config(encoder="tfidf", reranker="", **kw)


def test_pagerank_levels_and_legacy_graphs():
    nodes = [Node(i, i, "text", i, None) for i in "abc"]
    edge = Edge("a|b", "a", "b", "similar", "similar", False, 1)
    graph = Graph(nodes, [], [edge])
    assign_levels(graph)
    a, b, c = nodes
    assert a.pagerank == b.pagerank > c.pagerank
    assert [n.level for n in nodes] == ["top", "top", "bottom"]
    edge.user_directed = True
    assign_levels(graph)
    assert b.pagerank > a.pagerank == c.pagerank
    edge.status = "removed_irrelevant"
    legacy = graph.to_dict()
    for n in legacy["nodes"]:
        for field in ("level", "manual_level", "pagerank"):
            del n[field]
    loaded = final_graph_from_dict(legacy)
    assert all(n.level == "middle" and n.pagerank == pytest.approx(1/3) for n in loaded.nodes)
    assign_levels(Graph([], [], []))


def test_manual_level_survives_rebuild_and_approval(project, tmp_path):
    out = tmp_path / "levels"
    cfg = make_cfg(llm=False)
    before = pipeline.build(project, out, cfg, Preferences())["graph"]
    n = before.nodes[0]
    level = "bottom" if n.level == "top" else "top"
    item = {"type": "node_level", "node": n.path, "level": level}
    record = Record.load(out)
    with pytest.raises(ValueError):
        validate_events([{**item, "level": "unknown"}], record, set())
    edits = validate_events([item], record, set())
    after = pipeline.correct(out, cfg, new_feedback=edits)["graph"]
    updated = next(node for node in after.nodes if node.id == n.id)
    assert updated.level == level and updated.manual_level
    assert after.edges == before.edges and after.groups == before.groups
    assert [x for x in after.nodes if x.id != n.id] == [x for x in before.nodes if x.id != n.id]
    change, = feedback_changes(before, after, edits, cfg.corrector)["direct"]
    assert (change["from_level"], change["to_level"]) == (n.level, level)
    rebuilt = pipeline.build(project, out, cfg, Preferences())["graph"]
    assert rebuilt.to_dict() == after.to_dict()
    approved = approve_wiki(out, cfg, rebuilt.revision())
    assert json.loads((approved / "graph.json").read_text(encoding="utf-8")) == after.to_dict()
    assert any(f"level: {level}\n" in p.read_text(encoding="utf-8")
               and n.path in p.read_text(encoding="utf-8") for p in (approved / "wiki").glob("*.md"))


def test_ingest(project):
    files, chunks = ingest(project, make_cfg())
    paths = {f.path: f for f in files}
    assert "src/model.py:Zone.Identifier" not in paths
    assert paths["paper.pdf"].type == "pdf" and paths["Makefile"].type == "text"
    kinds = {c.kind for c in chunks if c.file_id == paths["src/model.py"].id}
    assert {"module", "class"} <= kinds
    assert any(c.kind == "path" for c in chunks if c.file_id == paths["fig.png"].id)
    assert any(r.kind == "wikilink" for r in paths["README.md"].refs)


def test_reference_candidates(project, tmp_path):
    out = tmp_path / "out"
    pipeline.build(project, out, make_cfg(llm=False), Preferences())
    rec = Record.load(out)
    pid = {f.path: f.id for f in rec.files}
    got = {(s, t, r) for s, t, r, _, _ in reference_candidates(rec)}
    assert (pid["src/train.py"], pid["src/model.py"], "imports") in got
    assert (pid["src/train.py"], pid["data_utils.py"], "imports") in got
    assert (pid["README.md"], pid["src/train.py"], "links_to") in got
    assert (pid["README.md"], pid["notes.md"], "links_to") in got
    assert (pid["paper.pdf"], pid["src/train.py"], "mentions") in got
    assert (pid["notes.md"], pid["results.csv"], "mentions") in got


def test_build_with_llm(project, tmp_path):
    out, fake = tmp_path / "out", FakeClaude()
    result = pipeline.build(project, out, make_cfg(), Preferences(purpose="발표 준비"), llm_client=fake)
    final = result["graph"]
    assert fake.calls > 0 and (out / "view.html").exists()
    assert all(n.summary for n in final.nodes if n.path != "src/__init__.py")
    assert {g.name for g in final.groups} == {"그룹"}
    assert any(e.relation == "uses" for e in final.edges)
    html = (out / "view.html").read_text(encoding="utf-8")
    assert "vis-network" in html and "/*__DATA__*/null" not in html
    calls = fake.calls
    pipeline.build(project, out, make_cfg(), Preferences(purpose="발표 준비"), llm_client=fake)
    assert fake.calls == calls  # second run is fully cached


def test_initial_preferences_shape_the_first_view(project, tmp_path):
    out = tmp_path / "guided"
    prefs = preferences_from_answers(Preferences(), "발표 준비", "실험 결과·그림, paper.pdf", "기존 폴더대로")
    result = pipeline.build(project, out, make_cfg(llm=False), prefs)
    graph = result["graph"]
    nodes = {n.path: n for n in graph.nodes}
    assert nodes["src/model.py"].group == nodes["src/train.py"].group != nodes["paper.pdf"].group
    assert json.loads((out / "prefs.json").read_text(encoding="utf-8"))["purpose"] == "발표 준비"

    first_view = result["view"].read_text(encoding="utf-8")
    reopened_view = pipeline.view(out).read_text(encoding="utf-8")
    for html in (first_view, reopened_view):
        embedded = html.split("const DATA = ", 1)[1].split(";\n", 1)[0]
        priority = json.loads(embedded)["meta"]["setup"]["files"]
        assert priority[0] == nodes["paper.pdf"].id
        assert {nodes["results.csv"].id, nodes["fig.png"].id} <= set(priority)
        assert nodes["src/train.py"].id not in priority


def test_structured_feedback_targets_exact_file_with_duplicate_names(project, tmp_path):
    (project / "src" / "notes.md").write_text("# Other notes", encoding="utf-8")
    (project / "README.md").write_text("# Demo\nSee [project notes](./notes.md).\n", encoding="utf-8")
    cfg = make_cfg(llm=False)
    out = tmp_path / "text_feedback"
    pipeline.build(project, out, cfg, Preferences())
    record = Record.load(out)
    edge_ids = {e.id for e in Graph.from_dict(json.loads((out / "graph.json").read_text(encoding="utf-8"))).edges}
    events = validate_events([{"type": "edge_irrelevant", "source": "README.md", "target": "notes.md"}], record, edge_ids)
    assert events[0].target == record.file_by_path["notes.md"].id
    result = pipeline.correct(out, cfg, record=record, new_feedback=events)
    assert any(e.status == "removed_irrelevant" for e in result["graph"].edges)


def test_explicit_edge_direction_survives_replay(project, tmp_path):
    out = tmp_path / "out"
    cfg = make_cfg(llm=False)
    graph = pipeline.build(project, out, cfg, Preferences())["graph"]
    edge = next(e for e in graph.edges if e.relation == "imports")
    record = Record.load(out)
    edit = {"type": "edge_add", "source": edge.target, "target": edge.source, "relation": "supports"}
    existing = {e.id for e in graph.edges}
    legacy = validate_events([edit], record, existing)
    renamed = pipeline.correct(out, cfg, new_feedback=legacy)["graph"]
    assert next(e for e in renamed.edges if e.id == edge.id).source == edge.source

    explicit = validate_events([{**edit, "set_direction": True, "edit_reason": "방향 교정"}], record, existing)
    pipeline.correct(out, cfg, new_feedback=explicit)
    rebuilt = pipeline.build(project, out, cfg, Preferences())["graph"]
    changed = next(e for e in rebuilt.edges if e.id == edge.id)
    assert (changed.source, changed.target, changed.user_directed) == (edge.target, edge.source, True)
    row, = feedback_changes(renamed, rebuilt, explicit, cfg.corrector)["direct"]
    assert row["action"] == "방향 반전" and row["reason"] == "방향 교정"
    assert row["previous_files"] == row["files"][::-1]


@pytest.mark.parametrize("direction", ["", "forward", "reverse"])
def test_first_view_uses_file_pair_choices(project, tmp_path, direction):
    out = tmp_path / "out"
    cfg = make_cfg(llm=False, corrector="best-of-n")
    prepared = pipeline.prepare_project(project, out, cfg)
    pairs = similar_file_pairs(prepared.record)
    assert len(pairs) == len({edge_key(*p) for p in pairs}) == 3
    record = prepared.record
    ids = [f.id for f in record.files if any(c.kind != "path" for c in record.file_chunks(f.id))]
    def similarity(pair):
        a, b = (record.file_index[i] for i in pair)
        return float(record.file_emb[a] @ record.file_emb[b])

    assert [similarity(p) for p in pairs] == pytest.approx(sorted(map(similarity, combinations(ids, 2)), reverse=True)[:3])
    assert not (out / "view.html").exists()
    assert pair_feedback(pairs, ["skip"] * 3) == []
    with pytest.raises(ValueError):
        pair_feedback(pairs, ["invalid"] * 3)

    events = pair_feedback(pairs, ["edge_confirm", "edge_irrelevant", "skip"], [direction, "reverse", "forward"])
    result = pipeline.build_prepared(prepared, out, cfg, Preferences(), events)
    a, b = pairs[0]
    edges = {e.id: e for e in result["graph"].edges}
    approved = edges[edge_key(a, b)]
    assert {approved.source, approved.target} == {a, b}
    assert approved.user_directed == bool(direction) and approved.status == "confirmed"
    if direction:
        assert (approved.source, approved.target) == ((b, a) if direction == "reverse" else (a, b))
    rejected = edges.get(edge_key(*pairs[1]))
    assert rejected is None or rejected.status == "removed_irrelevant"
    report = result["initial_changes"]
    assert len(report["direct"]) == 2 and report["automatic"]
    assert json.loads((out / "correction.json").read_text(encoding="utf-8"))["selection"]["rejections"] == 1
    replayed = pipeline.correct(out, cfg)["graph"]
    assert replayed.to_dict() == result["graph"].to_dict()


def test_reject_unproposed_initial_pair(project, tmp_path):
    out = tmp_path / "out"
    cfg = make_cfg(llm=False, corrector="best-of-n")
    prepared = pipeline.prepare_project(project, out, cfg)
    initial = pipeline.build_prepared(prepared, out, cfg, Preferences())["graph"]
    existing = {e.id for e in initial.edges}
    a, b = next((a.id, b.id) for a in initial.nodes for b in initial.nodes
                if a.id != b.id and edge_key(a.id, b.id) not in existing)
    result = pipeline.build_prepared(prepared, out, cfg, Preferences(), pair_feedback([(a, b)], ["edge_irrelevant"]))
    row, = result["initial_changes"]["direct"]
    assert row["before"] is None and row["after"] is None
    assert json.loads((out / "correction.json").read_text(encoding="utf-8"))["selection"]["rejections"] == 1


def test_approval_freezes_the_reviewed_version(project, tmp_path):
    out = tmp_path / "approval"
    cfg = make_cfg(llm=False, corrector="drift")
    original = pipeline.build(project, out, cfg, Preferences())["graph"]
    feedback = [FeedbackEvent(type="edge_confirm", source="README.md", target="src/train.py")]
    revised = pipeline.correct(out, cfg, new_feedback=feedback)["graph"]
    with pytest.raises(StaleGraphError):
        approve_wiki(out, cfg, original.revision())
    assert not (out / "approved_wiki").exists()

    result = approve_wiki(out, cfg, revised.revision())
    frozen = (result / "graph.json").read_bytes()
    assert frozen == (out / "final_graph.json").read_bytes()
    assert "<body data-approved>" in (result / "view.html").read_text(encoding="utf-8")
    assert (result / "wiki" / "README.md.md").is_file()

    pipeline.correct(out, cfg, new_feedback=[FeedbackEvent(
        type="edge_wrong", source="README.md", target="src/train.py")])
    assert (out / "final_graph.json").read_bytes() != frozen
    assert (result / "graph.json").read_bytes() == frozen


def test_group_lifecycle_preserves_files_and_edges(project, tmp_path):
    out = tmp_path / "groups"
    cfg = make_cfg(llm=False, corrector="best-of-n")
    original = pipeline.build(project, out, cfg, Preferences())["graph"]
    node = original.nodes[0].id
    gid = "user-test"
    def apply(event):
        return pipeline.correct(out, cfg, new_feedback=[event])["graph"]

    empty = apply(FeedbackEvent(type="group_add", group=gid, note="발표 자료"))
    assert next(g for g in empty.groups if g.id == gid).members == []
    moved = apply(FeedbackEvent(type="node_move", node=node, group=gid))
    assert next(g for g in moved.groups if g.id == gid).members == [node]
    final = apply(FeedbackEvent(type="group_delete", group=gid, note="발표 자료"))
    assert all(g.id != gid for g in final.groups)
    assert next(n for n in final.nodes if n.id == node).group is None
    assert {n.id for n in final.nodes} == {n.id for n in original.nodes}
    assert final.edges == original.edges
    assert pipeline.correct(out, cfg)["graph"] == final


def test_feedback_and_drift(project, tmp_path):
    out = tmp_path / "out"
    cfg = make_cfg(llm=False, corrector="drift", drift_margin=0.0)
    before = pipeline.build(project, out, cfg, Preferences())["graph"]
    rec = Record.load(out)
    pid = {f.path: f.id for f in rec.files}
    events = [
        FeedbackEvent(type="edge_confirm", source="src/train.py", target="src/model.py"),
        FeedbackEvent(type="edge_irrelevant", source="notes.md", target="results.csv"),
        FeedbackEvent(type="edge_wrong", source="paper.pdf", target="src/train.py"),
        FeedbackEvent(type="edge_add", source="notes.md", target="paper.pdf", relation="발표에 함께 쓸 자료"),
        FeedbackEvent(type="node_move", node="Makefile", group="빌드"),
        FeedbackEvent(type="edge_confirm", source="fig.png", target="data_utils.py", relation="uses"),
    ]
    final = pipeline.correct(out, cfg, new_feedback=events)["graph"]
    status = {e.id: e for e in final.edges}
    key = lambda a, b: "|".join(sorted([pid[a], pid[b]]))
    assert status[key("src/train.py", "src/model.py")].status == "confirmed"
    assert status[key("notes.md", "results.csv")].status == "removed_irrelevant"
    assert status[key("paper.pdf", "src/train.py")].status == "removed_wrong"
    added = status[key("notes.md", "paper.pdf")]
    assert added.origin == "user" and added.relation == "발표에 함께 쓸 자료"
    kept = status[key("fig.png", "data_utils.py")]  # confirmed although structure generation never proposed it
    assert kept.status == "confirmed" and kept.origin == "user" and kept.relation == "uses"
    node = next(n for n in final.nodes if n.path == "Makefile")
    assert next(g for g in final.groups if g.id == node.group).name == "빌드"
    assert any(e.correction for e in final.edges)  # drift explained the edges it changed
    changes = feedback_changes(before, final, resolve(events, rec), cfg.corrector)
    assert len(changes["direct"]) == 6 and changes["automatic"]
    direct_pairs = {frozenset(row["files"]) for row in changes["direct"]}
    assert all(frozenset(row["files"]) not in direct_pairs and row["before"] != row["after"]
               for row in changes["automatic"])
    # the log persists: a rebuild replays the same edits
    again = pipeline.build(project, out, cfg, Preferences())["graph"]
    assert {e.id: e.status for e in again.edges}[key("paper.pdf", "src/train.py")] == "removed_wrong"

    # 1안 method on the same feedback: a Bradley–Terry fit that rescores the untouched edges
    cfg.corrector = "align"
    aligned = pipeline.correct(out, cfg)["graph"]
    note = json.loads((out / "correction.json").read_text(encoding="utf-8"))["notes"][0]
    assert note.startswith("Bradley–Terry fit on 3 approved x 2 rejected")
    untouched = [e for e in aligned.edges if e.origin == "ai" and e.status in ("proposed", "removed_by_corrector")]
    assert untouched and all(0.0 <= e.score <= 1.0 for e in untouched)

    # stage report covers every stage and every registered corrector
    from projectwiki.srcs.report import report
    page = report(out).read_text(encoding="utf-8")
    assert "회의 파이프라인(1안 + 4안) 대비" in page and "<svg" in page
    assert all(name in page for name in ("baseline", "drift", "align"))
    assert page.count("유지됨") == 6


def test_pref_clusterer_anchors(project, tmp_path):
    out = tmp_path / "out"
    pipeline.build(project, out, make_cfg(llm=False, clusterer="pref"), Preferences())
    rec = Record.load(out)
    prefs = Preferences(anchors=["src/model.py", "notes.md"],
                        pairs=[{"a": "src/model.py", "b": "src/train.py", "score": 5}])
    groups = get_clusterer("pref", make_cfg()).cluster(rec, prefs)
    pid = {f.path: f.id for f in rec.files}
    assert pid["src/model.py"] in groups[0].members and pid["notes.md"] in groups[1].members
    assert pid["src/train.py"] in groups[0].members
    assert sorted(m for g in groups for m in g.members) == sorted(pid.values())


def test_plugin_and_obsidian(project, tmp_path):
    out = tmp_path / "out"
    cfg = make_cfg(llm=False, clusterer="projectwiki.models.clustering:BaselineClusterer")
    pipeline.build(project, out, cfg, Preferences())
    final = Graph.from_dict(json.loads((out / "final_graph.json").read_text(encoding="utf-8")))
    vault = export_obsidian(final, Record.load(out), tmp_path / "vault")
    note = (vault / "train.py.md").read_text(encoding="utf-8")
    assert "[[model.py]]" in note
