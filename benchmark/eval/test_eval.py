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
from graph_metrics import aggregate, evaluate, group_scores, level_order_accuracy, partition_ari  # noqa: E402
from gt_format import (GroundTruth, GTEdge, category, check_groupings, check_level_prefs, check_purposes,  # noqa: E402
                       level_map, load_preferences, pair_key, project_files, purpose_view,
                       apply_grouping, apply_levels, grouping_corrections, level_corrections, partition)
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
                     negatives=[{"a": "a.py", "b": "c.md"}], groups=[{"name": "code", "members": ["a.py", "b.py"]}],
                     levels={"top": ["a.py"], "middle": [], "bottom": ["b.py"]})
    gt.save(tmp_path / "gt.json")
    back = GroundTruth.load(tmp_path / "gt.json")
    assert back.edge_by_key[pair_key("b.py", "a.py")].personas == ["code"]
    assert back.negative_keys == {pair_key("a.py", "c.md")} and back.groups[0]["members"] == ["a.py", "b.py"]
    assert back.levels == {"top": ["a.py"], "middle": [], "bottom": ["b.py"]}


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
    purpose = {"id": "talk", "text": "results for a talk", "needed": [["r.md", "p.pdf"]], "optional": [["a.py", "r.md"]],
               "corrections": [{"op": "add", "a": "r.md", "b": "p.pdf"}]}
    assert check_purposes(gt, [purpose]) == []
    view = purpose_view(gt, purpose)
    edges = view.edge_by_key
    assert edges[pair_key("p.pdf", "r.md")].required  # needed: promoted to a key link
    assert edges[pair_key("a.py", "r.md")].required and edges[pair_key("a.py", "b.py")].required  # the rest: unchanged
    assert len(view.edges) == 3 and view.negative_keys == gt.negative_keys  # nothing dropped, nothing added
    assert not gt.edge_by_key[pair_key("p.pdf", "r.md")].required  # the input is left unchanged
    assert check_purposes(gt, [dict(purpose, corrections=[])]) != []  # the corrections must raise the weak needed link
    bad = dict(purpose, needed=[["a.py", "zzz.py"]], optional=[["a.py", "zzz.py"]], corrections=[])
    assert len(check_purposes(gt, [bad, bad])) == 5  # per copy: unknown pair, needed and optional; plus repeated id


def test_preference_files_match_ground_truth():
    """Every project: default levels in gt.json and two preferences of each kind, each a (preference, output) pair."""
    gt_root = EVAL.parent / "gt"
    projects = sorted(gt_root.glob("*/gt.json"))
    for gt_file in projects:
        gt, name = GroundTruth.load(gt_file), gt_file.parent.name
        purposes = load_preferences(gt_file.parent, "purposes")
        groupings = load_preferences(gt_file.parent, "groupings")
        levels = load_preferences(gt_file.parent, "levels")
        assert check_purposes(gt, purposes) == [], name
        assert check_groupings(gt, groupings) == [], name
        assert check_level_prefs(gt, levels) == [], name  # also checks the default levels
        assert len(purposes) == 2 and {p["base"] for p in purposes} == {"docs", "code"}, name
        assert len(groupings) == 2 and len(levels) == 2 and gt.levels, name
        assert all("groups" not in p and "levels" not in p for p in purposes), name  # links only


def test_groupings_and_levels():
    groups = [{"name": "code", "members": ["a.py", "b.py"]}, {"name": "docs", "members": ["r.md", "p.pdf"]}]
    default = {"top": ["a.py"], "middle": ["r.md"], "bottom": ["b.py", "p.pdf"]}
    gt = GroundTruth(project="t", edges=[GTEdge("a.py", "b.py", "uses")], groups=groups, levels=default)
    assert project_files(gt) == {"a.py", "b.py", "r.md", "p.pdf"}
    grouping = {"id": "stage", "text": "group by stage",
                "groups": [{"name": "talk", "members": ["b.py", "r.md", "p.pdf"]}, {"name": "rest", "members": ["a.py"]}]}
    level = {"id": "results", "text": "results on top", "levels": {"top": ["r.md"], "middle": ["b.py"], "bottom": ["a.py", "p.pdf"]}}
    grouping["corrections"] = grouping_corrections(groups, grouping["groups"])
    level["corrections"] = level_corrections(default, level["levels"])
    assert check_groupings(gt, [grouping]) == [] and check_level_prefs(gt, [level]) == []
    assert check_groupings(gt, [dict(grouping, corrections=[])]) != []  # corrections must give the output
    assert level_map(level["levels"]) == {"r.md": 3, "b.py": 2, "a.py": 1, "p.pdf": 1}
    assert partition_ari(groups, groups) == 1.0 and partition_ari(groups, grouping["groups"]) < 1.0
    lv = level_map(level["levels"])
    assert level_order_accuracy(lv, lv) == 1.0
    assert level_order_accuracy({}, lv) == 0.5  # no levels at all: every pair is a tie
    assert level_order_accuracy({f: 4 - v for f, v in lv.items()}, lv) == 0.0
    bad_groups = dict(grouping, groups=[{"name": "g", "members": ["a.py", "a.py", "zzz.py"]}, {"name": "g", "members": []}])
    problems = check_groupings(gt, [bad_groups])
    for text in ("group name repeated", "a.py is in more than one group", "zzz.py is not a project file", "b.py is in no group"):
        assert any(text in p for p in problems), text
    bad_levels = dict(level, levels={"top": ["r.md", "zzz.py"], "middle": ["r.md"], "low": []})
    problems = check_level_prefs(gt, [bad_levels])
    for text in ("unknown level 'low'", "r.md is on more than one level", "zzz.py is not a project file", "a.py has no level"):
        assert any(text in p for p in problems), text
    gt_missing = GroundTruth(project="t", groups=groups, levels={"top": ["a.py"]})
    assert any("default levels" in p for p in check_level_prefs(gt_missing, []))


def test_corrections_replay():
    """Grouping and level corrections: computed from a default and an output, replayed, they give the output back."""
    default = [{"name": "code", "members": ["a.py", "b.py", "c.py"]}, {"name": "docs", "members": ["r.md", "n.md"]}]
    wanted = [{"name": "core", "members": ["a.py"]}, {"name": "rest", "members": ["b.py", "c.py", "r.md", "n.md"]}]
    ops = grouping_corrections(default, wanted)
    assert partition(apply_grouping(default, ops)) == partition(wanted)
    assert [o["op"] for o in ops].count("move") == 3 and ops[-1] == {"op": "delete_group", "name": "docs"}
    levels = {"top": ["a.py"], "middle": ["r.md"], "bottom": ["b.py"]}
    target = {"top": ["r.md"], "middle": ["a.py"], "bottom": ["b.py"]}
    ops = level_corrections(levels, target)
    assert ops == [{"op": "set_level", "file": "a.py", "importance": 2}, {"op": "set_level", "file": "r.md", "importance": 3}]
    assert apply_levels(levels, ops) == target
