import json
from types import SimpleNamespace

import pymupdf
import pytest

from projectwiki import pipeline
from projectwiki.cluster import get_clusterer
from projectwiki.config import Config
from projectwiki.graph import reference_candidates
from projectwiki.ingest import ingest
from projectwiki.record import Record
from projectwiki.schema import FeedbackEvent, Graph, Preferences
from projectwiki.viz import export_obsidian


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


def test_feedback_and_drift(project, tmp_path):
    out = tmp_path / "out"
    cfg = make_cfg(llm=False, corrector="drift", drift_margin=0.0)
    pipeline.build(project, out, cfg, Preferences())
    rec = Record.load(out)
    pid = {f.path: f.id for f in rec.files}
    events = [
        FeedbackEvent(type="edge_confirm", source="src/train.py", target="src/model.py"),
        FeedbackEvent(type="edge_irrelevant", source="notes.md", target="results.csv"),
        FeedbackEvent(type="edge_wrong", source="paper.pdf", target="src/train.py"),
        FeedbackEvent(type="edge_add", source="notes.md", target="paper.pdf", relation="발표에 함께 쓸 자료"),
        FeedbackEvent(type="node_move", node="Makefile", group="빌드"),
    ]
    final = pipeline.correct(out, cfg, new_feedback=events)["graph"]
    status = {e.id: e for e in final.edges}
    key = lambda a, b: "|".join(sorted([pid[a], pid[b]]))
    assert status[key("src/train.py", "src/model.py")].status == "confirmed"
    assert status[key("notes.md", "results.csv")].status == "removed_irrelevant"
    assert status[key("paper.pdf", "src/train.py")].status == "removed_wrong"
    added = status[key("notes.md", "paper.pdf")]
    assert added.origin == "user" and added.relation == "발표에 함께 쓸 자료"
    node = next(n for n in final.nodes if n.path == "Makefile")
    assert next(g for g in final.groups if g.id == node.group).name == "빌드"
    assert any(e.correction for e in final.edges)  # drift explained the edges it changed
    # the log persists: a rebuild replays the same edits
    again = pipeline.build(project, out, cfg, Preferences())["graph"]
    assert {e.id: e.status for e in again.edges}[key("paper.pdf", "src/train.py")] == "removed_wrong"

    # 1안 method on the same feedback: a Bradley–Terry fit that rescores the untouched edges
    cfg.corrector = "align"
    aligned = pipeline.correct(out, cfg)["graph"]
    note = json.loads((out / "correction.json").read_text(encoding="utf-8"))["notes"][0]
    assert note.startswith("Bradley–Terry fit on 2 approved x 2 rejected")
    untouched = [e for e in aligned.edges if e.origin == "ai" and e.status in ("proposed", "removed_by_corrector")]
    assert untouched and all(0.0 <= e.score <= 1.0 for e in untouched)

    # stage report covers every stage and every registered corrector
    from projectwiki.report import report
    page = report(out).read_text(encoding="utf-8")
    assert "회의 파이프라인(1안 + 4안) 대비" in page and "<svg" in page
    assert all(name in page for name in ("baseline", "drift", "align"))
    assert page.count("유지됨") == 5


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
    cfg = make_cfg(llm=False, clusterer="projectwiki.cluster.baseline:BaselineClusterer")
    pipeline.build(project, out, cfg, Preferences())
    final = Graph.from_dict(json.loads((out / "final_graph.json").read_text(encoding="utf-8")))
    vault = export_obsidian(final, Record.load(out), tmp_path / "vault")
    note = (vault / "train.py.md").read_text(encoding="utf-8")
    assert "[[model.py]]" in note
