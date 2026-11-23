"""Score every system on every benchmark project and run the virtual-user simulation.

    python benchmark/eval/run_eval.py [--seeds 5] [--budgets 0 1 2 4 8 16]   # -> runs/bench/results/

Systems (graphs read from finished runs):
  pipeline   runs/bench/<p>/final_graph.json        bge-m3 + reranker + Claude judge (no feedback)
  no-LLM     runs/bench_nollm/<p>/final_graph.json  the same candidates without the Claude judge
  LLM-only   runs/bench/<p>/llm_only_graph.json     one Claude call over file summaries (llm_only_baseline.py)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

EVAL = Path(__file__).resolve().parent
ROOT = EVAL.parents[1]
HERE = ROOT / "benchmark"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(EVAL))

from projectwiki.config import Config  # noqa: E402
from projectwiki.models.preference import CORRECTORS  # noqa: E402
from projectwiki.schema import Graph  # noqa: E402
from graph_metrics import aggregate, evaluate, markdown_table  # noqa: E402
from gt_format import GroundTruth  # noqa: E402
from projectwiki.srcs.record import Record  # noqa: E402
from feedback_sim import PERSONAS, curve_svg, simulate  # noqa: E402

RUNS = ROOT / "runs"
SYSTEMS = {"pipeline": ("bench", "final_graph.json"), "no-LLM": ("bench_nollm", "final_graph.json"),
           "LLM-only": ("bench", "llm_only_graph.json")}
COLS = [("precision", "P"), ("recall", "R"), ("f1", "F1"), ("precision_strict", "P strict"), ("f1_strict", "F1 strict"),
        ("precision_strict_hideable", "P strict (hideable)"), ("recall_grouped", "R grouped"), ("f1_grouped", "F1 grouped"),
        ("edges_per_file", "lines/file"), ("between_per_slot", "between-group lines/slot"), ("recall_explicit", "R explicit"),
        ("recall_semantic", "R semantic"), ("relation_accuracy", "Rel acc"), ("relation_accuracy_coarse", "Rel acc (4)"),
        ("typed_f1", "Typed F1"), ("direction_accuracy", "Dir acc"), ("direction_coverage", "Dir coverage"), ("evidence_grounded", "Grounded"), ("group_ari", "Group ARI"),
        ("predicted", "#pred"), ("unjudged_predicted", "#unjudged")]


def load_graph(path: Path) -> Graph | None:
    return Graph.from_dict(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--budgets", type=int, nargs="+", default=[0, 1, 2, 4, 8, 16])
    args = ap.parse_args()
    all_names = sorted(p.parent.name for p in (HERE / "gt").glob("*/gt.json"))
    all_names = [n for n in all_names if not n.startswith("mock_")] + [n for n in all_names if n.startswith("mock_")]
    names = [n for n in all_names if (RUNS / "bench" / n / "graph.json").exists()]
    missing = [n for n in all_names if n not in names]
    if missing:
        print(f"no build for {len(missing)} project(s), skipped: {', '.join(missing)}\n"
              f"  build them first (benchmark/README.md, '실행'), e.g. projectwiki build benchmark/gt/{missing[0]}/project "
              f"-o runs/bench/{missing[0]}")
    if not names:
        raise SystemExit("nothing to evaluate")
    scores = {sys_: {} for sys_ in SYSTEMS}
    sims, gts = {}, {}
    for name in names:
        gt = gts[name] = GroundTruth.load(HERE / "gt" / name / "gt.json")
        record = Record.load(RUNS / "bench" / name)
        for sys_, (run, file) in SYSTEMS.items():
            g = load_graph(RUNS / run / name / file)
            if g is not None:
                scores[sys_][name] = evaluate(g, gt, record)
        graph = load_graph(RUNS / "bench" / name / "graph.json")
        cfg = Config.load(RUNS / "bench" / name / "config.json")
        sims[name] = simulate(graph, record, gt, cfg, list(CORRECTORS), args.budgets, args.seeds)
        print(f"{name}: " + "  ".join(f"{s} F1={scores[s][name]['f1']:.3f}" for s in SYSTEMS
                                       if name in scores[s] and scores[s][name]["f1"] is not None))

    out_dir = RUNS / "bench" / "results"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "scores.json").write_text(json.dumps(scores, indent=1), encoding="utf-8")
    (out_dir / "simulation.json").write_text(json.dumps(sims, indent=1), encoding="utf-8")

    groups = {"real projects": [n for n in names if not n.startswith("mock_")],
              "mock projects": [n for n in names if n.startswith("mock_")]}
    groups = {g: ns for g, ns in groups.items() if ns}
    md = [f"# Benchmark results\n\nGenerated {time.strftime('%Y-%m-%d %H:%M')} by `benchmark/run_eval.py` on "
          f"{len(names)} projects ({', '.join(f'{len(ns)} {g}' for g, ns in groups.items())}). Percentages. "
          "P counts judged pairs only; real projects use pooled labels, mock projects a closed world "
          "(see benchmark/README.md).\n"]
    for group, ns in groups.items():
        agg = {s: aggregate({n: r[n] for n in ns if n in r}) for s, r in scores.items() if any(n in r for n in ns)}
        md += [f"## Graph accuracy, {group} (macro average)\n",
               markdown_table({s: {c[0]: a.get("macro_" + c[0], a.get(c[0])) for c in COLS} for s, a in agg.items()}, COLS),
               "\nMicro (summed counts): " + ", ".join(
                   f"{s} P {100 * a['micro_precision']:.1f} / R {100 * a['micro_recall']:.1f} / F1 {100 * a['micro_f1']:.1f}"
                   for s, a in agg.items() if a["micro_f1"] is not None) + "\n"]
        per_file = [sum(e.required for e in gts[n].edges) / sum(len(g["members"]) for g in gts[n].groups)
                    for n in ns if gts[n].groups]
        if per_file:
            md.append(f"For comparison, drawing only the ground truth's key links gives {sum(per_file) / len(per_file):.2f} "
                      "lines per file and 1.00 between-group line per linked pair of groups.\n")
    md += ["## F1 per project\n",
           "| project | " + " | ".join(SYSTEMS) + " |\n|---|" + "---:|" * len(SYSTEMS) + "\n" + "".join(
               f"| {n} | " + " | ".join(f"{100 * scores[s][n]['f1']:.1f}" if n in scores[s] and scores[s][n]["f1"] is not None
                                         else "–" for s in SYSTEMS) + " |\n" for n in names)]
    last = args.budgets[-1]
    for group, ns in groups.items():
        md.append(f"\n## Virtual-user feedback, {group} (held-out F1, mean over projects and seeds)\n")
        tag = "real" if group.startswith("real") else "mock"
        for persona in PERSONAS:
            series, rows = {}, {}
            for c in CORRECTORS:
                def mean_of(metric, k):
                    v = [sims[n][persona][c][k][metric]["mean"] for n in ns
                         if sims[n][persona][c][k][metric]["mean"] is not None]
                    return sum(v) / len(v) if v else None
                series[c] = [(k, mean_of("f1", k)) for k in args.budgets]
                rows[c] = {"f1_0": series[c][0][1], "f1_k": series[c][-1][1], "typed_k": mean_of("typed_f1", last),
                           "compliance": mean_of("compliance", last), "relabel": mean_of("adherence_relabel", last),
                           "collateral": mean_of("collateral", last), "fixed": mean_of("fixed", last)}
            base_k = rows.get("baseline", {}).get("f1_k")
            for c in rows:  # same events and held-out pairs as baseline, so the gap is the generalization
                rows[c]["delta"] = rows[c]["f1_k"] - base_k if None not in (rows[c]["f1_k"], base_k) else None
            svg = curve_svg(series, f"{group}, persona: {persona}")
            (out_dir / f"feedback_{tag}_{persona}.svg").write_text(svg, encoding="utf-8")
            md.append(f"### persona: {persona}\n\n![](feedback_{tag}_{persona}.svg)\n\n" + markdown_table(rows, [
                ("f1_0", "F1 (k=0)"), ("f1_k", f"F1 (k={last})"), ("delta", f"Δ vs baseline (k={last})"),
                ("typed_k", f"typed F1 (k={last})"), ("compliance", "edits kept"), ("relabel", "relation fixes kept"),
                ("collateral", "correct edges lost"), ("fixed", "wrong edges removed")]) + "\n")
    md.append("\nHeld-out F1 rises for every method, baseline included, because the simulated user corrects "
              "mistakes and those pairs leave the held-out set. Only the gap to baseline at the same k measures "
              "how far a method generalizes the feedback.\n")
    (out_dir / "RESULTS.md").write_text("\n".join(md), encoding="utf-8")
    print(f"-> {out_dir / 'RESULTS.md'}")


if __name__ == "__main__":
    main()
