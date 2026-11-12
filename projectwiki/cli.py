"""Command line: build, correct, view, report, obsidian, doctor."""
from __future__ import annotations

import argparse
import json
import logging
import os
import webbrowser
from pathlib import Path

from . import pipeline
from .config import Config
from .models.visualization import export_obsidian
from .schema import Graph, Preferences
from .srcs import doctor
from .srcs.feedback import read_events
from .srcs.record import Record


def load_dotenv() -> None:
    """Read KEY=VALUE lines from ./.env or the repository's .env without overriding the environment."""
    for path in (Path.cwd() / ".env", Path(__file__).resolve().parents[1] / ".env"):
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip("\"'"))
            return


def load_config(args) -> Config:
    cfg = Config.load(Path(args.config)) if getattr(args, "config", None) else Config()
    overrides = {"encoder": args.encoder, "clusterer": args.clusterer, "corrector": args.corrector,
                 "llm_model": args.llm_model, "language": args.language, "llm_backend": args.llm_backend}
    for k, v in overrides.items():
        if v is not None:
            setattr(cfg, k, v)
    if args.no_llm:
        cfg.llm = False
    if args.no_rerank:
        cfg.reranker = ""
    return cfg


def load_prefs(args) -> Preferences:
    prefs = Preferences(**json.loads(Path(args.prefs).read_text(encoding="utf-8"))) if args.prefs else Preferences()
    if args.purpose:
        prefs.purpose = args.purpose
    return prefs


def show(path: Path, open_it: bool) -> None:
    print(f"viewer: {path}")
    if open_it:
        webbrowser.open(path.resolve().as_uri())


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="projectwiki", description="Project folder -> relation graph pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="run the whole pipeline on a project folder")
    b.add_argument("root", help="project folder")
    b.add_argument("-o", "--out", help="output folder (default: <root>/.projectwiki)")
    b.add_argument("--purpose", help="the user's purpose for this project")
    b.add_argument("--prefs", help="clustering preferences JSON; pairs.score=1-5 means desire to group together")
    b.add_argument("--config", help="JSON file with Config fields")
    b.add_argument("--encoder", choices=["bge-m3", "tfidf"])
    b.add_argument("--clusterer", help="registered name or package.module:Class")
    b.add_argument("--corrector", help="registered name or package.module:Class")
    b.add_argument("--llm-backend", choices=["api", "cli"],
                   help="cli: logged-in Claude Code CLI, no API key (default) / api: ANTHROPIC_API_KEY")
    b.add_argument("--llm-model", help="model for relation judgment and image descriptions")
    b.add_argument("--language", help="language of summaries and labels (default Korean)")
    b.add_argument("--no-llm", action="store_true", help="skip all Claude stages")
    b.add_argument("--no-rerank", action="store_true", help="choose evidence by cosine only")
    b.add_argument("--open", action="store_true", help="open the viewer in a browser")

    c = sub.add_parser("correct", help="apply feedback again (preference, final graph, viewer) without re-reading files")
    c.add_argument("out", help="output folder of a build")
    c.add_argument("--feedback", nargs="*", default=[], help="feedback.jsonl files exported from the viewer")
    c.add_argument("--corrector", help="registered name or package.module:Class")
    c.add_argument("--open", action="store_true")

    v = sub.add_parser("view", help="re-render view.html from final_graph.json")
    v.add_argument("out")
    v.add_argument("--open", action="store_true")

    o = sub.add_parser("obsidian", help="export the final graph as an Obsidian vault")
    o.add_argument("out")
    o.add_argument("vault")

    sub.add_parser("doctor", help="check packages, GPU, cached models and the LLM backend")

    r = sub.add_parser("report", help="write stages.html: each stage's output, checked against the meeting plan")
    r.add_argument("out")
    r.add_argument("--open", action="store_true")

    load_dotenv()
    args = p.parse_args(argv)
    if args.cmd == "doctor":
        raise SystemExit(doctor.run())
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    for noisy in ("httpx", "httpx2", "httpcore", "anthropic", "urllib3", "huggingface_hub", "filelock"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    if args.cmd == "build":
        root = Path(args.root).resolve()
        out = Path(args.out).resolve() if args.out else root / ".projectwiki"
        result = pipeline.build(root, out, load_config(args), load_prefs(args))
        show(result["view"], args.open)
    elif args.cmd == "correct":
        out = Path(args.out).resolve()
        cfg = Config.load(out / "config.json")
        if args.corrector:
            cfg.corrector = args.corrector
            cfg.save(out / "config.json")
        events = [e for f in args.feedback for e in read_events(Path(f))]
        result = pipeline.correct(out, cfg, new_feedback=events)
        show(result["view"], args.open)
    elif args.cmd == "view":
        show(pipeline.view(Path(args.out).resolve()), args.open)
    elif args.cmd == "obsidian":
        out = Path(args.out).resolve()
        final = Graph.from_dict(json.loads((out / "final_graph.json").read_text(encoding="utf-8")))
        print(f"vault: {export_obsidian(final, Record.load(out), Path(args.vault))}")
    elif args.cmd == "report":
        from .srcs.report import report
        path = report(Path(args.out).resolve())
        print(f"report: {path}")
        if args.open:
            webbrowser.open(path.as_uri())


if __name__ == "__main__":
    main()
