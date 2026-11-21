"""Virtual-user feedback: how well each preference method (models/preference.py) generalizes a few corrections.

A simulated user is an oracle built from ground truth, the protocol of active pairwise-constrained clustering
(Basu, Banerjee & Mooney, SDM 2004). It looks at the graph a viewer shows and gives k feedback events:

- edge_wrong on a shown pair judged unrelated (remove)
- edge_irrelevant on a shown pair that is related but outside the persona's interest (remove)
- edge_add on a required pair of interest that is not shown (add)
- relabel: edge_add with the right relation on a shown pair of interest whose relation type is wrong (modify)
- edge_confirm on a shown, correctly typed pair of interest (sampled less often: people mostly fix mistakes)

Personas: all (every ground-truth edge matters), code (a technical worker: by default links among code,
notebooks and configs) and docs (a document-oriented worker: links that involve a document, paper or figure).
Mock projects tag each designed edge with the personas it matters to, and those tags take precedence.

Two kinds of score:
- adherence: did the final graph do exactly what each event asked (shown or hidden, and the requested relation
  for relabel)? finalize() should make this 100% for every method; it is reported per event kind.
- generalization: scores on held-out pairs, the judged pairs no event touched. The oracle mostly picks
  mistakes, which then leave the held-out set, so held-out F1 rises even for baseline; compare a method with
  baseline at the same k (same events) to see how far it generalizes.
"""
from __future__ import annotations

import random
from copy import deepcopy

import numpy as np

from gt_format import GroundTruth, category, pair_key
from graph_metrics import evaluate, predicted
from projectwiki.config import Config
from projectwiki.models.preference import Correction, get_corrector
from projectwiki.schema import VISIBLE_STATUS, FeedbackEvent, Graph
from projectwiki.srcs.finalize import finalize
from projectwiki.srcs.record import Record

CODE_SIDE = {"code", "notebook", "config"}
PERSONAS = ("all", "code", "docs")


def persona_view(gt: GroundTruth, persona: str) -> GroundTruth:
    """Ground truth as one persona sees it: edges outside its interest become negatives for it."""
    if persona == "all":
        return gt

    def wanted(e) -> bool:
        if e.personas:  # designed in mock projects
            return persona in e.personas
        both_code = category(e.a) in CODE_SIDE and category(e.b) in CODE_SIDE
        return both_code if persona == "code" else not both_code
    view = deepcopy(gt)
    view.edges = [e for e in gt.edges if wanted(e)]
    view.negatives = gt.negatives + [{"a": e.a, "b": e.b, "source": "persona", "note": "off-interest"}
                                     for e in gt.edges if not wanted(e)]
    return view


def feedback_pool(shown: dict, gt: GroundTruth, view: GroundTruth) -> list[tuple[float, dict]]:
    """(weight, event) pairs the oracle could give for the graph it is shown."""
    full, want, neg = gt.edge_by_key, view.edge_by_key, gt.negative_keys
    pool = []
    for k, (a, b, e) in shown.items():
        if k in want and want[k].accepts(e.relation):
            pool.append((1.0, {"type": "edge_confirm", "a": a, "b": b, "kind": "confirm"}))
        elif k in want:
            pool.append((3.0, {"type": "edge_add", "a": a, "b": b, "relation": want[k].relation, "kind": "relabel"}))
        elif k in full:
            pool.append((3.0, {"type": "edge_irrelevant", "a": a, "b": b, "kind": "remove"}))
        elif k in neg:
            pool.append((3.0, {"type": "edge_wrong", "a": a, "b": b, "kind": "remove"}))
    for k, e in want.items():
        if e.required and k not in shown:
            pool.append((3.0, {"type": "edge_add", "a": e.a, "b": e.b, "relation": e.relation, "kind": "add"}))
    return pool


EVENT_KINDS = ("add", "remove", "relabel", "confirm")


def adhered(p: dict, final_shown: dict) -> bool:
    """Whether the final graph does what the event asked."""
    k = pair_key(p["a"], p["b"])
    if p["kind"] == "remove":
        return k not in final_shown
    if p["kind"] == "relabel":
        return k in final_shown and final_shown[k][2].relation == p["relation"]
    return k in final_shown


def sample(pool: list[tuple[float, dict]], k: int, rng: random.Random) -> list[dict]:
    """Weighted sampling without replacement."""
    pool, out = list(pool), []
    for _ in range(min(k, len(pool))):
        i = rng.choices(range(len(pool)), weights=[w for w, _ in pool])[0]
        out.append(pool.pop(i)[1])
    return out


def to_events(picked: list[dict], record: Record) -> list[FeedbackEvent]:
    fid = {f.path: f.id for f in record.files}
    return [FeedbackEvent(type=p["type"], source=fid[p["a"]], target=fid[p["b"]], relation=p.get("relation"))
            for p in picked]


def run_one(graph: Graph, record: Record, gt: GroundTruth, view: GroundTruth, cfg: Config, corrector: str,
            picked: list[dict], before: set[str]) -> dict:
    events = to_events(picked, record)
    correction = get_corrector(corrector, cfg).correct(graph, events, record) if events else Correction()
    final = finalize(graph, correction, events, cfg)
    final_shown = predicted(final, VISIBLE_STATUS)
    after = set(final_shown)
    touched = {pair_key(p["a"], p["b"]) for p in picked}
    judged = set(view.edge_by_key) | view.negative_keys
    held = judged - touched
    score = evaluate(final, view, record, keys=held)
    want, neg = set(view.edge_by_key), view.negative_keys
    good_before = {k for k in before & held if k in want}
    bad_before = {k for k in before & held if k in neg}
    ok = [adhered(p, final_shown) for p in picked]
    by_kind = {f"adherence_{kind}": (float(np.mean([o for o, p in zip(ok, picked) if p["kind"] == kind]))
                                     if any(p["kind"] == kind for p in picked) else None) for kind in EVENT_KINDS}
    return {"f1": score["f1"], "precision": score["precision"], "recall": score["recall"],
            "typed_f1": score["typed_f1"], "relation_accuracy": score["relation_accuracy"],
            "compliance": float(np.mean(ok)) if ok else None, **by_kind,
            "collateral": len(good_before - after) / len(good_before) if good_before else None,
            "fixed": len(bad_before - after) / len(bad_before) if bad_before else None,
            "hidden": len(correction.hide), "events": len(events),
            **{f"n_{kind}": sum(p["kind"] == kind for p in picked) for kind in EVENT_KINDS}}


def simulate(graph: Graph, record: Record, gt: GroundTruth, cfg: Config, correctors: list[str],
             budgets: list[int], seeds: int = 5, personas: tuple = PERSONAS) -> dict:
    """result[persona][corrector][k] = mean and std of each score over seeds."""
    base = finalize(graph, Correction(), [], cfg)
    shown = predicted(base)
    before = set(shown)
    out = {}
    for persona in personas:
        view = persona_view(gt, persona)
        pool = feedback_pool(shown, gt, view)
        out[persona] = {"pool": len(pool)}
        for name in correctors:
            rows = {}
            for k in budgets:
                runs = [run_one(graph, record, gt, view, cfg, name, sample(pool, k, random.Random(s)), before)
                        for s in range(seeds if k else 1)]
                rows[k] = {m: summarize([r[m] for r in runs]) for m in runs[0]}
            out[persona][name] = rows
    return out


def summarize(vals: list) -> dict:
    v = [x for x in vals if x is not None]
    return {"mean": float(np.mean(v)) if v else None, "std": float(np.std(v)) if v else None, "n": len(v)}


# ---- report --------------------------------------------------------------------------------------
COLORS = ["#2f6fdb", "#d1495b", "#1f8a4c", "#b7791f", "#7b4fd6", "#5f6b7a"]


def curve_svg(series: dict[str, list[tuple[int, float]]], title: str, width: int = 520, height: int = 300) -> str:
    """Held-out score against the number of feedback events, one line per method."""
    xs = sorted({x for pts in series.values() for x, _ in pts})
    ys = [y for pts in series.values() for _, y in pts if y is not None]
    if not xs or not ys:
        return ""
    lo, hi = min(ys), max(ys)
    lo, hi = max(0.0, lo - 0.05), min(1.0, hi + 0.05)
    L, R, T, B = 48, 120, 28, 36
    px = {x: L + i * (width - L - R) / max(1, len(xs) - 1) for i, x in enumerate(xs)}

    def py(y):
        return T + (hi - y) / (hi - lo or 1) * (height - T - B)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" font-family="sans-serif" font-size="11">',
             f'<text x="{L}" y="16" font-size="12" font-weight="600">{title}</text>']
    for t in np.linspace(lo, hi, 5):
        parts.append(f'<line x1="{L}" x2="{width - R}" y1="{py(t):.1f}" y2="{py(t):.1f}" stroke="#ddd"/>'
                     f'<text x="{L - 6}" y="{py(t) + 4:.1f}" text-anchor="end" fill="#666">{t:.2f}</text>')
    for x in xs:
        parts.append(f'<text x="{px[x]:.1f}" y="{height - B + 16}" text-anchor="middle" fill="#666">{x}</text>')
    parts.append(f'<text x="{(L + width - R) / 2:.0f}" y="{height - 6}" text-anchor="middle" fill="#666">feedback events</text>')
    for i, (name, pts) in enumerate(series.items()):
        c = COLORS[i % len(COLORS)]
        pts = [(x, y) for x, y in pts if y is not None]
        d = " ".join(f"{px[x]:.1f},{py(y):.1f}" for x, y in pts)
        parts.append(f'<polyline points="{d}" fill="none" stroke="{c}" stroke-width="2"/>')
        parts += [f'<circle cx="{px[x]:.1f}" cy="{py(y):.1f}" r="3" fill="{c}"/>' for x, y in pts]
        parts.append(f'<text x="{width - R + 10}" y="{T + 14 + 16 * i}" fill="{c}" font-weight="600">{name}</text>')
    parts.append("</svg>")
    return "".join(parts)
