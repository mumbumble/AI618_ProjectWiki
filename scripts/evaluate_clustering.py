"""Compare clustering methods on a saved project record; no model downloads or LLM calls."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Allow execution from an uninstalled checkout as well as an editable install.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from projectwiki.config import Config
from projectwiki.schema import Preferences
from projectwiki.srcs.cluster_eval import compare_clusterers, parameter_sensitivity
from projectwiki.srcs.record import Record


def load_pairs(path: Path) -> list:
    data = json.loads(path.read_text(encoding="utf-8"))
    pairs = data.get("pairs") if isinstance(data, dict) else data
    if not isinstance(pairs, list):
        raise ValueError(f"{path}: expected a JSON list of ratings, or an object with pairs")
    return pairs


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path, help="build output containing record/, config.json and prefs.json")
    parser.add_argument("--prefs", type=Path, help="training preferences (default: <out>/prefs.json)")
    parser.add_argument("--test", type=Path, required=True, help="held-out ratings, never used in fitting")
    parser.add_argument("--validation", type=Path, help="separate ratings to select metric_l2")
    parser.add_argument("--l2-grid", nargs="+", type=float, help="requires --validation; default: 0.01 0.1 1.0")
    parser.add_argument("--config", type=Path, help="override saved Config; e.g. metric_use_type=false for ablation")
    parser.add_argument("--methods", nargs="+", help="default: baseline pref metric; also constrained graph hdbscan")
    parser.add_argument("--tasks", type=Path, help="report-only onboarding checklists (JSON list of name/files)")
    parser.add_argument("--html", type=Path, help="also write a self-contained group/task comparison report")
    parser.add_argument("--sensitivity", action="store_true", help="report a fixed parameter grid for the three new methods")
    parser.add_argument("-o", "--output", type=Path, help="report JSON (default: <out>/clustering_eval.json)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    try:
        prefs = Preferences(**json.loads((args.prefs or args.out / "prefs.json").read_text(encoding="utf-8")))
        cfg = Config.load(args.config or args.out / "config.json")
        record, test_pairs = Record.load(args.out), load_pairs(args.test)
        tasks = json.loads(args.tasks.read_text(encoding="utf-8")) if args.tasks else None
        if tasks is not None and not isinstance(tasks, list):
            raise ValueError("onboarding tasks must be a JSON list")
        result = compare_clusterers(record, prefs, test_pairs, cfg,
                                   load_pairs(args.validation) if args.validation else None, args.l2_grid,
                                   methods=args.methods, tasks=tasks)
        if args.sensitivity:
            result["sensitivity"] = parameter_sensitivity(record, prefs, test_pairs, cfg, tasks)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    output = args.output or args.out / "clustering_eval.json"
    # This tool only writes its report, preserving the saved graph and feedback.
    inputs = {p.resolve() for p in (args.test, args.prefs or args.out / "prefs.json",
                                    args.config or args.out / "config.json")}
    if args.validation:
        inputs.add(args.validation.resolve())
    if args.tasks:
        inputs.add(args.tasks.resolve())
    reserved = {args.out.resolve() / name for name in
                ("config.json", "prefs.json", "graph.json", "final_graph.json", "feedback.jsonl",
                 "clustering_info.json", "run_info.json", "correction.json", "view.html", "stages.html")}
    protected_dirs = {args.out.resolve() / name for name in ("record", "cache")}
    for target in [output] + ([args.html] if args.html else []):
        if target.resolve() in inputs | reserved or protected_dirs.intersection(target.resolve().parents):
            parser.error("output must not overwrite input files or saved build artifacts")
    if args.html and args.html.resolve() == output.resolve():
        parser.error("JSON and HTML reports must use different output files")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print("method        test RMSE   pair accuracy   groups   file coverage")
    for name, metrics in result["methods"].items():
        accuracy = metrics["pair_accuracy"]
        accuracy_text = f"{accuracy:.3f}" if accuracy is not None else "n/a"
        rmse = f"{metrics['distance_rmse']:.3f}" if metrics["distance_rmse"] is not None else "n/a"
        print(f"{name:13} {rmse:>5}       {accuracy_text:>5}           {metrics['group_count']:>3}      {metrics['file_coverage']:.1%}")
    print(f"report: {output}")
    if args.html:
        from projectwiki.srcs.cluster_report import write_comparison_html
        write_comparison_html(record, result, args.html)
        print(f"HTML: {args.html}")


if __name__ == "__main__":
    main()
