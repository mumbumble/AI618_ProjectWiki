"""Tests of the evaluation code. Run: pytest benchmark/eval"""
import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parent
ROOT = EVAL.parents[1]  # repository root
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(EVAL))
sys.path.insert(0, str(ROOT / "tests"))

from projectwiki import pipeline  # noqa: E402
from projectwiki.schema import Edge, Evidence, Graph, Node, Preferences  # noqa: E402
from graph_metrics import aggregate, evaluate, group_scores  # noqa: E402
from gt_format import GroundTruth, GTEdge, category, check_purposes, load_purposes, pair_key, purpose_view  # noqa: E402
from projectwiki.srcs.record import Record  # noqa: E402
from feedback_sim import persona_view, simulate  # noqa: E402
from test_pipeline import make_cfg, project  # noqa: E402,F401  (pytest fixture)


def build(project, tmp_path):
    out = tmp_path / "out"
    pipeline.build(project, out, make_cfg(llm=False), Preferences())
    return out, Record.load(out), Graph.from_dict(__import__("json").loads((out / "graph.json").read_text()))


def test_category():
    assert category("src/a.py") == "code" and category("Makefile") == "code"
    assert category("x.ipynb") == "notebook" and category("p.pdf") == "paper"
    assert category("docs/a.md") == "doc" and category("f.png") == "image" and category("c.yaml") == "config"


def test_ground_truth_roundtrip(tmp_path):
    gt = GroundTruth(project="t", edges=[GTEdge("a.py", "b.py", "uses", personas=["code"])],
                     negatives=[{"a": "a.py", "b": "c.md"}], groups=[{"name": "code", "members": ["a.py", "b.py"]}])
    gt.save(tmp_path / "gt.json")
    back = GroundTruth.load(tmp_path / "gt.json")
    assert back.edge_by_key[pair_key("b.py", "a.py")].personas == ["code"]
    assert back.negative_keys == {pair_key("a.py", "c.md")} and back.groups[0]["members"] == ["a.py", "b.py"]


def node(p):
    return Node(id=p, path=p, type="text", title=p, group=None)


def edge(a, b, rel, status="proposed", quote=""):
    return Edge(id=pair_key(a, b), source=a, target=b, relation=rel, reason="similar", direct=False, score=1.0,
                status=status, evidence=[Evidence("c", a, "", quote)] if quote else [])


def test_evaluate_counts():
    paths = ["a.py", "b.py", "doc.md", "c.py", "d.md"]
    g = Graph(nodes=[node(p) for p in paths], groups=[], edges=[
        edge("a.py", "b.py", "uses", quote="import b"),      # tp, right type, right direction
        edge("doc.md", "a.py", "same_topic"),                # tp, wrong type (coarse also wrong)
        edge("c.py", "d.md", "uses"),                        # fp (judged unrelated)
        edge("b.py", "c.py", "uses"),                        # unjudged
        edge("a.py", "d.md", "other", status="llm_rejected"),  # not shown, ignored
    ])
    gt = GroundTruth(project="t", edges=[
        GTEdge("a.py", "b.py", "uses", layer="explicit"),
        GTEdge("doc.md", "a.py", "describes"),
        GTEdge("a.py", "c.py", "uses"),                      # missed
        GTEdge("doc.md", "d.md", "same_topic", required=False),  # optional, missed without penalty
    ], negatives=[{"a": "c.py", "b": "d.md"}])
    r = evaluate(g, gt)
    assert (r["tp"], r["fp"], r["fn"], r["unjudged_predicted"]) == (2, 1, 1, 1)
    assert r["precision"] == 2 / 3 and r["recall"] == 2 / 3 and r["precision_strict"] == 2 / 3
    assert r["recall_explicit"] == 1.0 and r["recall_semantic"] == 0.5
    assert r["relation_accuracy"] == 0.5 and r["direction_accuracy"] == 1.0
    assert r["evidence_grounded"] == 0.25 and r["relation_conformance"] == 1.0
    agg = aggregate({"t": r, "u": r})
    assert agg["micro_precision"] == 2 / 3 and agg["macro_f1"] == r["f1"]


def test_grouped_recall_and_hideable_precision():
    # groups: lib = {lib.py, util.py}, tut = {t1.ipynb, t2.ipynb}; one required representative pair lib-tut
    paths = ["lib.py", "util.py", "t1.ipynb", "t2.ipynb"]
    imp = edge("t2.ipynb", "util.py", "uses")
    imp.reason = "imports"                                   # a fact the system cannot hide
    g = Graph(nodes=[node(p) for p in paths], groups=[], edges=[
        edge("lib.py", "util.py", "uses"),                   # within-group required: found
        imp,                                                 # a different real pair between lib and tut
    ])
    gt = GroundTruth(project="t", edges=[
        GTEdge("lib.py", "util.py", "uses"),
        GTEdge("t1.ipynb", "lib.py", "uses"),                # the representative cross-group pair: missed
        GTEdge("t2.ipynb", "util.py", "uses", required=False, layer="explicit"),
        GTEdge("t1.ipynb", "t2.ipynb", "same_topic"),         # within-group required: missed
    ], groups=[{"name": "lib", "members": ["lib.py", "util.py"]},
               {"name": "tut", "members": ["t1.ipynb", "t2.ipynb"]}])
    r = evaluate(g, gt)
    assert r["recall"] == 1 / 3                              # only lib-util among 3 required pairs
    assert (r["grouped_found"], r["grouped_units"]) == (2, 3)  # lib-util + the lib-tut slot, of 2 within + 1 slot
    assert r["precision_strict"] == 1 / 2                    # the optional import counts against strict precision
    assert r["precision_strict_hideable"] == 1.0             # but not when only hideable edges count
    assert r["direction_judged"] == 2 and r["direction_coverage"] == 1.0  # both matched pairs have a direction
    assert r["edges_per_file"] == 2 / 4                      # 2 lines shown over 4 files
    assert (r["between_predicted"], r["between_slots"], r["between_per_slot"]) == (1, 1, 1.0)  # one line per linked pair
    agg = aggregate({"t": r})
    assert agg["micro_recall_grouped"] == 2 / 3


def test_group_scores():
    g = Graph(nodes=[Node(id=p, path=p, type="text", title=p, group=grp) for p, grp in
                     (("a.py", "g1"), ("b.py", "g1"), ("c.md", "g2"), ("d.md", None))], groups=[], edges=[])
    perfect = GroundTruth(project="t", groups=[{"name": "x", "members": ["a.py", "b.py"]},
                                               {"name": "y", "members": ["c.md"]}, {"name": "z", "members": ["d.md"]}])
    assert group_scores(g, perfect)["group_ari"] == 1.0
    assert group_scores(g, GroundTruth(project="t"))["group_ari"] is None


def test_simulate_keeps_edits_and_scores_held_out(project, tmp_path):
    out, record, graph = build(project, tmp_path)
    path = {n.id: n.path for n in graph.nodes}
    explicit = [GTEdge(path[e.source], path[e.target], "uses", layer="explicit") for e in graph.edges
                if e.reason in ("imports", "links_to", "mentions")]
    gt = GroundTruth(project="t", edges=explicit)
    shown = {pair_key(*[n.path for n in graph.nodes if n.id in (e.source, e.target)]) for e in graph.edges}
    gt.negatives = [{"a": k.split("|")[0], "b": k.split("|")[1]} for k in shown if k not in gt.edge_by_key]
    res = simulate(graph, record, gt, make_cfg(llm=False), ["baseline", "drift", "align"], [0, 2, 4], seeds=2)
    for persona in ("all", "code", "docs"):
        for c in ("baseline", "drift", "align"):
            assert res[persona][c][0]["events"]["mean"] == 0
            for k in (2, 4):
                for m in ("compliance", "adherence_add", "adherence_remove", "adherence_relabel"):
                    v = res[persona][c][k][m]["mean"]
                    assert v is None or v == 1.0  # explicit edits, relation fixes included, are always replayed
    code_view = persona_view(gt, "code")
    assert all(category(e.a) in {"code", "notebook", "config"} for e in code_view.edges)


def test_purpose_view():
    gt = GroundTruth(project="t", edges=[GTEdge("a.py", "b.py", "uses"), GTEdge("a.py", "r.md", "describes"),
                                         GTEdge("p.pdf", "r.md", "supports", required=False)],
                     negatives=[{"a": "a.py", "b": "x.md"}])
    purpose = {"id": "talk", "text": "results for a talk", "needed": [["r.md", "p.pdf"]], "optional": [["a.py", "r.md"]]}
    assert check_purposes(gt, [purpose]) == []
    view = purpose_view(gt, purpose)
    edges = view.edge_by_key
    assert edges[pair_key("p.pdf", "r.md")].required  # needed: required even if the edge was optional
    assert not edges[pair_key("a.py", "r.md")].required  # optional: never penalized
    assert pair_key("a.py", "b.py") not in edges and pair_key("a.py", "b.py") in view.negative_keys
    assert pair_key("a.py", "x.md") in view.negative_keys and len(gt.edges) == 3  # the input is left unchanged
    bad = dict(purpose, needed=[["a.py", "zzz.py"]], optional=[["a.py", "zzz.py"]])
    assert len(check_purposes(gt, [bad, bad])) == 5  # per copy: unknown pair, needed and optional; plus repeated id


def test_purpose_files_match_ground_truth():
    gt_root = EVAL.parent / "gt"
    found = 0
    for gt_file in sorted(gt_root.glob("*/gt.json")):
        purposes = load_purposes(gt_file.parent)
        found += len(purposes)
        assert check_purposes(GroundTruth.load(gt_file), purposes) == [], gt_file.parent.name
    assert found >= 4
