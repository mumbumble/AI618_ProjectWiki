"""Command-line interface for csvdelta."""

import argparse
import csv
import json
import os
import sys

try:
    import tomllib
except ImportError:  # Python 3.9 and 3.10
    import tomli as tomllib

from core import Differ, DiffResult, summarize
from io import read_table, write_delta

DEFAULT_CONFIG = "configs/default.toml"
DEFAULTS = {
    "key_columns": [],
    "delimiter": ",",
    "encoding": "utf-8",
    "output_format": "text",
    "float_tolerance": 0.0,
    "max_rows_in_memory": 500000,
    "color": True,
}
EXIT_SAME, EXIT_DIFF, EXIT_ERROR = 0, 1, 2


def load_config(path=None):
    settings = dict(DEFAULTS)
    if path is None and not os.path.exists(DEFAULT_CONFIG):
        return settings
    with open(path or DEFAULT_CONFIG, "rb") as fh:
        settings.update(tomllib.load(fh))
    return settings


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", metavar="PATH", help="TOML settings file (default: configs/default.toml)")
    common.add_argument("--key", action="append", metavar="COL", help="key column, repeatable")
    common.add_argument("--delimiter", help="field delimiter")
    common.add_argument("--encoding", help="file encoding")
    common.add_argument("--format", choices=["text", "json", "html"], help="output format")
    common.add_argument("--output", metavar="PATH", help="file to write for json or html output")
    common.add_argument("--ignore-case", action="store_true", help="compare strings case-insensitively")
    common.add_argument("--tolerance", type=float, help="numeric tolerance")

    parser = argparse.ArgumentParser(prog="csvdelta", description="Show row- and cell-level differences between CSV files.")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("diff", "summary"):
        p = sub.add_parser(name, parents=[common])
        p.add_argument("a")
        p.add_argument("b")
    p = sub.add_parser("patch", parents=[common])
    p.add_argument("a")
    p.add_argument("delta")
    return parser


def fmt_key(key):
    if isinstance(key, (list, tuple)):
        return ",".join(str(k) for k in key)
    return str(key)


def render_text(result, color):
    red, green, yellow, reset = ("\033[31m", "\033[32m", "\033[33m", "\033[0m") if color else ("", "", "", "")
    lines = []
    for change in result.row_changes:
        if change.kind == "added":
            lines.append(f"{green}+ key={fmt_key(change.key)}{reset}")
        elif change.kind == "removed":
            lines.append(f"{red}- key={fmt_key(change.key)}{reset}")
        else:
            for cell in change.cells:
                lines.append(f"{yellow}~ key={fmt_key(change.key)} {cell.column}: {cell.old} -> {cell.new}{reset}")
    return "\n".join(lines)


def lower_table(table):
    table.rows = [[c.lower() if isinstance(c, str) else c for c in row] for row in table.rows]
    return table


def apply_delta(table, delta, keys):
    pos = [table.header.index(k) for k in keys]
    gone = {tuple(str(r[i]) for i in pos) for r in delta["removed"]}
    changes = {}
    for ch in delta["changed"]:
        k = ch["key"] if isinstance(ch["key"], list) else [ch["key"]]
        changes[tuple(str(v) for v in k)] = ch["cells"]
    out = []
    for row in table.rows:
        k = tuple(str(row[i]) for i in pos)
        if k in gone:
            continue
        for cell in changes.get(k, []):
            row[table.header.index(cell["column"])] = cell["new"]
        out.append(row)
    out.extend(delta["added"])
    return out


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        cfg = load_config(args.config)
        keys = args.key or cfg["key_columns"] or None
        tol = args.tolerance if args.tolerance is not None else cfg["float_tolerance"]
        delim = args.delimiter or cfg["delimiter"]
        enc = args.encoding or cfg["encoding"]
        fmt = args.format or cfg["output_format"]
        color = cfg["color"] and sys.stdout.isatty()

        if args.command == "patch":
            table = read_table(args.a, delimiter=delim, encoding=enc)
            with open(args.delta, encoding="utf-8") as fh:
                delta = json.load(fh)
            rows = apply_delta(table, delta, keys or table.header[:1])
            out = open(args.output, "w", newline="", encoding="utf-8") if args.output else sys.stdout
            writer = csv.writer(out)
            writer.writerow(table.header)
            writer.writerows(rows)
            if args.output:
                out.close()
            return EXIT_SAME

        table_a = read_table(args.a, delimiter=delim, encoding=enc)
        table_b = read_table(args.b, delimiter=delim, encoding=enc)
        if args.ignore_case:
            table_a, table_b = lower_table(table_a), lower_table(table_b)
        result = Differ(key=keys, tolerance=tol).run(table_a, table_b)

        if args.command == "summary":
            print(json.dumps(summarize(result), indent=2))
        elif fmt == "text":
            print(render_text(result, color))
        else:
            if not args.output:
                raise ValueError("--output PATH is required for json and html formats")
            write_delta(result, args.output, fmt=fmt)
        return EXIT_DIFF if result.row_changes else EXIT_SAME
    except (OSError, KeyError, ValueError) as exc:
        print(f"csvdelta: error: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
