"""One-shot LLM baseline: Claude sees every file's path and summary and writes the whole relation graph at once.

    python benchmark/eval/llm_only_baseline.py runs/bench/nanogpt [--model claude-haiku-5-5]

No retrieval, no evidence selection and no per-edge judgment: this is "just using an LLM" for the same task.
It reads the summaries from a finished build and writes <out>/llm_only_graph.json in the pipeline's graph
format, so run_eval.py scores it like the other systems.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from projectwiki.config import Config  # noqa: E402
from projectwiki.pipeline import make_llm  # noqa: E402
from projectwiki.schema import RELATIONS, Edge, Graph, Node, edge_key  # noqa: E402
from projectwiki.srcs.llm import obj_schema  # noqa: E402
from projectwiki.srcs.record import Record  # noqa: E402

SYSTEM = """You map how the files of one project folder relate, for someone who wants to understand the project.
List the links between files that such a reader would want: one file imports, runs, configures, documents,
implements, evaluates, produces or extends another; a paper and the code that realizes it; a figure and what makes
or uses it. Leave out pairs that only share a folder or generic words.
relation: implements, describes, uses, produces, extends, same_method, supports, contradicts, compares,
same_topic, duplicate, other. direction: a_to_b if it reads "A <relation> B", b_to_a, or both."""


def run(out: Path, model: str | None) -> Path:
    cfg = Config.load(out / "config.json")
    if model:
        cfg.llm_model = model
    record = Record.load(out)
    paths = [f.path for f in record.files]
    lines = []
    for f in record.files:
        text = f.summary or " ".join(c.text for c in record.file_chunks(f.id))[:300]
        lines.append(f"- {f.path} [{f.type}{', ' + f.role if f.role else ''}]: {' '.join(text.split())}")
    schema = obj_schema(edges={"type": "array", "items": obj_schema(
        a={"type": "string", "enum": paths}, b={"type": "string", "enum": paths},
        relation={"type": "string", "enum": RELATIONS},
        direction={"type": "string", "enum": ["a_to_b", "b_to_a", "both"]},
        label={"type": "string"})})
    content = "Files in the project:\n" + "\n".join(lines)
    llm = make_llm(replace(cfg, llm=True), out / "llm_only")
    r = llm.json(cfg.llm_model, SYSTEM, content, schema, key=content, max_tokens=16000)
    llm.save()
    if r is None:
        raise SystemExit(f"{out}: the model returned no graph")
    ids = {f.path: f.id for f in record.files}
    edges: dict[str, Edge] = {}
    for x in r["edges"]:
        a, b = ids[x["a"]], ids[x["b"]]
        if a == b:
            continue
        if x["direction"] == "b_to_a":
            a, b = b, a
        edges.setdefault(edge_key(a, b), Edge(id=edge_key(a, b), source=a, target=b, relation=x["relation"],
                                              reason="llm_only", direct=False, score=1.0, label=x["label"]))
    nodes = [Node(id=f.id, path=f.path, type=f.type, title=f.title, group=None, role=f.role, summary=f.summary)
             for f in record.files]
    path = out / "llm_only_graph.json"
    path.write_text(json.dumps(Graph(nodes=nodes, groups=[], edges=list(edges.values())).to_dict(),
                               ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{out.name}: {len(edges)} edges ({llm.cost_report()}) -> {path}")
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", nargs="+", type=Path, help="finished build folder(s)")
    ap.add_argument("--model", help="default: the build's llm_model")
    args = ap.parse_args()
    for out in args.out:
        run(out, args.model)


if __name__ == "__main__":
    main()
