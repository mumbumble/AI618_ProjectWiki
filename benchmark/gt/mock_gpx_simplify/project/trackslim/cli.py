"""Command-line interface for trackslim.

Examples:
    trackslim simplify ride.gpx ride_small.gpx --tolerance 8.0
    trackslim simplify hike.gpx hike_small.gpx --plugin elevation_guard
    trackslim stats hike.gpx
"""

import argparse
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python 3.9 and 3.10
    import tomli as tomllib

from core import Simplifier, compression_ratio
from io import read_gpx, write_gpx
from plugins import PLUGINS

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "configs" / "default.toml"


def load_config(path):
    with open(path, "rb") as fh:
        return tomllib.load(fh)


def total_ascent(track):
    gain = 0.0
    for prev, cur in zip(track.points, track.points[1:]):
        if cur.ele > prev.ele:
            gain += cur.ele - prev.ele
    return gain


def build_simplifier(cfg, tolerance, plugin_name):
    params = dict(
        tolerance_m=tolerance,
        turn_weight=cfg["turn_weight"],
        elev_weight=cfg["elev_weight"],
        min_turn_deg=cfg["min_turn_deg"],
    )
    if not plugin_name:
        return Simplifier(**params)
    if plugin_name not in PLUGINS:
        known = ", ".join(sorted(PLUGINS)) or "none"
        sys.exit(f"error: unknown plugin '{plugin_name}' (available: {known})")
    return PLUGINS[plugin_name](**params)


def cmd_simplify(args):
    config = load_config(args.config)
    cfg = config["simplify"]
    tolerance = args.tolerance if args.tolerance is not None else cfg["tolerance_m"]
    plugin_name = args.plugin or config.get("plugin", {}).get("name", "")

    track = read_gpx(args.input)
    simplifier = build_simplifier(cfg, tolerance, plugin_name)
    result = simplifier.simplify(track)
    write_gpx(result, args.output)

    ratio = compression_ratio(track.points, result.points)
    print(f"{len(track.points)} -> {len(result.points)} points "
          f"(ratio {ratio:.3f}) written to {args.output}")
    return 0


def cmd_stats(args):
    config = load_config(args.config)
    tol = config["simplify"]["tolerance_m"]

    track = read_gpx(args.input)
    preview = build_simplifier(config["simplify"], tol, "").simplify(track)

    print(f"file:          {args.input}")
    print(f"name:          {track.name or '-'}")
    print(f"points:        {len(track.points)}")
    print(f"total ascent:  {total_ascent(track):.1f} m")
    print(f"preview ratio: {compression_ratio(track.points, preview.points):.3f} "
          f"(tolerance {tol} m)")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="trackslim",
        description="Simplify GPX tracks while keeping turns and elevation changes.",
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                        help="TOML config file (default: configs/default.toml)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_simp = sub.add_parser("simplify", help="simplify a GPX track")
    p_simp.add_argument("input", type=Path)
    p_simp.add_argument("output", type=Path)
    p_simp.add_argument("--tolerance", type=float, default=None,
                        help="tolerance in metres")
    p_simp.add_argument("--plugin", default="",
                        help="plugin name, e.g. elevation_guard")
    p_simp.set_defaults(func=cmd_simplify)

    p_stats = sub.add_parser("stats", help="print track statistics")
    p_stats.add_argument("input", type=Path)
    p_stats.set_defaults(func=cmd_stats)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except OSError as exc:
        sys.exit(f"error: {exc}")


if __name__ == "__main__":
    sys.exit(main())
