"""Score a relation graph against ground truth (gt_format.py).

Metrics, following Text2KGBench (Mihindukulasooriya et al., ISWC 2023) where they apply:

- edge P / R / F1 on file pairs. Precision counts only judged pairs (locally closed world); recall counts
  required edges. Optional edges are correct when predicted and never missed. Strict precision counts a
  predicted optional (weak) edge as a mistake, so a system cannot gain by proposing every loosely related pair.
- recall by layer: explicit (imports, links, file-name mentions) vs semantic (judged by a person).
- relation accuracy on matched pairs, exact (12 types, or a type the ground truth also accepts) and coarse
  (4 classes), plus typed F1 where a true positive needs the right type.
- direction accuracy where the ground truth has a direction and the predicted type is the primary one, with its
  coverage (the share of type-matched pairs whose direction could be judged).
- grouped recall: required edges inside a group count one by one, but each pair of groups linked by a required
  edge is one slot, found when any ground-truth edge between those two groups is predicted. The ground truth picks
  one representative pair per group pair, and a person recalls "the tutorials use the library", not which pair.
- hideable strict precision: strict precision over edges the system can hide. Imports and links are facts that
  stay visible (schema.STRUCTURAL), so predicting an optional import is not a choice the system made.
- graph complexity of what the viewer shows: lines per file, and lines between ground-truth groups per group pair
  linked in the ground truth (1.0 when a system draws one line per linked pair of groups, as the key links do).
  Lower is simpler; read it next to recall, since drawing fewer lines is only good when the key links stay.
- relation conformance: the share of predicted relations from schema.RELATIONS (Text2KGBench's ontology
  conformance; the inverse of its relation hallucination).
- evidence grounding: the share of predicted edges with a quote found verbatim in the record (the analogue of
  Text2KGBench's subject/object hallucination checks against the source text).
- per purpose (purposes.json): group ARI against the purpose's groups, and level order accuracy, the share of file
  pairs on different ground-truth levels that a predicted level puts in the same order (ties count half, so a
  view without levels scores 50%).
"""
from __future__ import annotations

from collections import Counter

from gt_format import COARSE, GroundTruth, pair_key
from projectwiki.schema import RELATIONS, STRUCTURAL, VISIBLE_STATUS, Graph
from projectwiki.srcs.record import Record


def f1(p: float | None, r: float | None) -> float | None:
    if p is None or r is None:
        return None
    return 0.0 if p + r == 0 else 2 * p * r / (p + r)


def ratio(a: int, b: int) -> float | None:
    return a / b if b else None


def predicted(graph: Graph, statuses=VISIBLE_STATUS) -> dict:
    """pair key -> (source path, target path, edge) for the edges a viewer shows."""
    path = {n.id: n.path for n in graph.nodes}
    out = {}
    for e in graph.edges:
        if e.status in statuses and e.source in path and e.target in path:
            out[pair_key(path[e.source], path[e.target])] = (path[e.source], path[e.target], e)
    return out


def grounded(edge, record: Record | None) -> bool:
    quotes = [v for v in edge.evidence if v.quote]
    if record is None:
        return bool(quotes)
    for v in quotes:
        c = record.chunk_by_id.get(v.chunk_id)
        if c is not None and " ".join(v.quote.split()).lower() in " ".join(c.text.split()).lower():
            return True
    return False


def group_scores(graph: Graph, gt: GroundTruth) -> dict:
    """Agreement of the graph's groups with the ground-truth groups (adjusted Rand index, NMI).

    Ungrouped files count as their own singleton group. None when either side has no groups."""
    if not gt.groups or all(n.group is None for n in graph.nodes):
        return {"group_ari": None, "group_nmi": None}
    from sklearn.metrics import adjusted_rand_score, normalized_mutual_info_score
    truth = {m: i for i, g in enumerate(gt.groups) for m in g["members"]}
    nodes = [n for n in graph.nodes if n.path in truth]
    pred = [n.group if n.group is not None else f"_single_{n.path}" for n in nodes]
    gold = [truth[n.path] for n in nodes]
    return {"group_ari": float(adjusted_rand_score(gold, pred)), "group_nmi": float(normalized_mutual_info_score(gold, pred))}


def partition_ari(a: list[dict], b: list[dict]) -> float | None:
    """Adjusted Rand index between two groupings ([{"name", "members"}]) over the files both contain."""
    from sklearn.metrics import adjusted_rand_score
    ga = {m: i for i, g in enumerate(a) for m in g["members"]}
    gb = {m: i for i, g in enumerate(b) for m in g["members"]}
    files = sorted(ga.keys() & gb.keys())
    return float(adjusted_rand_score([ga[f] for f in files], [gb[f] for f in files])) if files else None


def level_order_accuracy(pred: dict[str, float], gold: dict[str, int]) -> float | None:
    """Share of file pairs on different gold levels that pred orders the same way; a tie in pred counts half.
    Files missing from pred count as tied with everything. None when gold has no such pair."""
    files = sorted(gold)
    agree, pairs = 0.0, 0
    for i, a in enumerate(files):
        for b in files[i + 1:]:
            if gold[a] == gold[b]:
                continue
            pairs += 1
            pa, pb = pred.get(a), pred.get(b)
            if pa is None or pb is None or pa == pb:
                agree += 0.5
            elif (pa > pb) == (gold[a] > gold[b]):
                agree += 1
    return agree / pairs if pairs else None


def group_pair(a: str, b: str, group_of: dict[str, str]) -> frozenset | None:
    """The two ground-truth groups a pair spans, or None when both files share a group or one is ungrouped."""
    ga, gb = group_of.get(a), group_of.get(b)
    return None if ga is None or gb is None or ga == gb else frozenset((ga, gb))


def grouped_recall(pred: dict, gold: dict, required: set[str], gt: GroundTruth) -> tuple[int, int]:
    """(found, units): within-group required edges one by one plus one slot per group pair (see module doc)."""
    if not gt.groups:
        return 0, 0
    group_of = {m: g["name"] for g in gt.groups for m in g["members"]}
    within = [k for k in required if group_pair(gold[k].a, gold[k].b, group_of) is None]
    slots = {group_pair(gold[k].a, gold[k].b, group_of) for k in required} - {None}
    hit_slots = {group_pair(gold[k].a, gold[k].b, group_of) for k in pred if k in gold} & slots
    return sum(k in pred for k in within) + len(hit_slots), len(within) + len(slots)


def evaluate(graph: Graph, gt: GroundTruth, record: Record | None = None, keys: set[str] | None = None,
             statuses=VISIBLE_STATUS) -> dict:
    """Score `graph`; `keys` restricts scoring to those pairs (held-out pairs in simulate.py)."""
    pred = predicted(graph, statuses)
    gold = gt.edge_by_key
    neg = gt.negative_keys
    if keys is not None:
        pred = {k: v for k, v in pred.items() if k in keys}
        gold = {k: v for k, v in gold.items() if k in keys}
        neg = neg & keys
    required = {k for k, e in gold.items() if e.required}

    tp = [k for k in pred if k in gold]
    fp = [k for k in pred if k in neg]
    unjudged = [k for k in pred if k not in gold and k not in neg]
    hit_required = [k for k in tp if k in required]
    p = ratio(len(tp), len(tp) + len(fp))
    r = ratio(len(hit_required), len(required))
    # strict: only required edges count as correct; optional (weak) ones count against precision
    weak = [k for k in tp if k not in required]
    p_strict = ratio(len(hit_required), len(hit_required) + len(weak) + len(fp))

    # strict precision over edges the system can hide (imports and links always stay visible)
    hideable = {k for k, v in pred.items() if v[2].reason not in STRUCTURAL}
    h_hit, h_weak, h_fp = (sum(k in hideable for k in x) for x in (hit_required, weak, fp))
    p_strict_hideable = ratio(h_hit, h_hit + h_weak + h_fp)
    g_found, g_units = grouped_recall(pred, gold, required, gt)
    r_grouped = ratio(g_found, g_units)

    # complexity: lines per file, and lines between ground-truth groups per linked pair of groups
    group_of = {m: g["name"] for g in gt.groups for m in g["members"]}
    slots = {group_pair(gold[k].a, gold[k].b, group_of) for k in required} - {None}
    between_pred = sum(group_pair(v[0], v[1], group_of) is not None for v in pred.values())

    rel_ok = [k for k in tp if gold[k].accepts(pred[k][2].relation)]
    coarse_ok = [k for k in tp if COARSE.get(pred[k][2].relation) == COARSE.get(gold[k].relation)
                 or any(COARSE.get(pred[k][2].relation) == COARSE.get(x) for x in gold[k].also)]
    typed_p = ratio(len(rel_ok), len(tp) + len(fp))
    typed_r = ratio(sum(k in required for k in rel_ok), len(required))
    directed = [k for k in rel_ok if gold[k].direction in ("a_to_b",) and pred[k][2].relation == gold[k].relation]
    dir_ok = [k for k in directed if (pred[k][0], pred[k][1]) == (gold[k].a, gold[k].b)]

    by_layer = {}
    for layer in ("explicit", "semantic"):
        req = {k for k in required if gold[k].layer == layer}
        by_layer[layer] = {"required": len(req), "found": sum(k in pred for k in req),
                           "recall": ratio(sum(k in pred for k in req), len(req))}

    confusion = Counter((gold[k].relation, pred[k][2].relation) for k in tp)
    groups = group_scores(graph, gt)
    return {
        **groups,
        "predicted": len(pred), "judged_predicted": len(tp) + len(fp), "unjudged_predicted": len(unjudged),
        "gold_edges": len(gold), "gold_required": len(required), "negatives": len(neg),
        "tp": len(tp), "fp": len(fp), "fn": len(required) - len(hit_required),
        "precision": p, "recall": r, "f1": f1(p, r),
        "precision_strict": p_strict, "f1_strict": f1(p_strict, r), "weak_predicted": len(weak),
        "precision_strict_hideable": p_strict_hideable, "hideable_predicted": len(hideable),
        "recall_grouped": r_grouped, "f1_grouped": f1(p, r_grouped), "grouped_units": g_units, "grouped_found": g_found,
        "edges_per_file": ratio(len(pred), len(group_of)), "between_predicted": between_pred,
        "between_slots": len(slots), "between_per_slot": ratio(between_pred, len(slots)),
        "recall_explicit": by_layer["explicit"]["recall"], "recall_semantic": by_layer["semantic"]["recall"],
        "layers": by_layer,
        "relation_accuracy": ratio(len(rel_ok), len(tp)), "relation_accuracy_coarse": ratio(len(coarse_ok), len(tp)),
        "typed_precision": typed_p, "typed_recall": typed_r, "typed_f1": f1(typed_p, typed_r),
        "direction_accuracy": ratio(len(dir_ok), len(directed)), "direction_judged": len(directed),
        "direction_coverage": ratio(len(directed), len(rel_ok)),
        "relation_conformance": ratio(sum(v[2].relation in RELATIONS for v in pred.values()), len(pred)),
        "evidence_grounded": ratio(sum(grounded(v[2], record) for v in pred.values()), len(pred)),
        "confusion": [[g, q, n] for (g, q), n in confusion.most_common()],
        "missed": sorted(k for k in required if k not in pred),
        "false_positives": sorted(fp),
        "unjudged": sorted(unjudged),
    }


SUM_KEYS = ("predicted", "judged_predicted", "unjudged_predicted", "gold_required", "tp", "fp", "fn", "grouped_units",
            "grouped_found")


def aggregate(results: dict[str, dict]) -> dict:
    """Micro scores from summed counts and macro scores averaged over projects."""
    tot = {k: sum(r[k] for r in results.values()) for k in SUM_KEYS}
    p = ratio(tot["tp"], tot["tp"] + tot["fp"])
    r = ratio(tot["gold_required"] - tot["fn"], tot["gold_required"])
    rg = ratio(tot["grouped_found"], tot["grouped_units"])
    out = {**tot, "micro_precision": p, "micro_recall": r, "micro_f1": f1(p, r), "micro_recall_grouped": rg,
           "micro_f1_grouped": f1(p, rg)}
    for key in ("precision", "recall", "f1", "precision_strict", "f1_strict", "precision_strict_hideable",
                "recall_grouped", "f1_grouped", "edges_per_file", "between_per_slot", "recall_explicit", "recall_semantic",
                "relation_accuracy",
                "relation_accuracy_coarse", "typed_f1", "direction_accuracy", "direction_coverage", "relation_conformance",
                "evidence_grounded", "group_ari", "group_nmi"):
        vals = [x[key] for x in results.values() if x[key] is not None]
        out[f"macro_{key}"] = sum(vals) / len(vals) if vals else None
    return out


def fmt(x, pct: bool = True) -> str:
    if x is None:
        return "–"
    return f"{100 * x:.1f}" if pct else str(x)


PLAIN = {"edges_per_file", "between_per_slot"}  # counts per file or per slot, not percentages


def cell(key: str, x) -> str:
    if key in PLAIN and x is not None:
        return f"{x:.2f}"
    return fmt(x, not isinstance(x, int))


def markdown_table(rows: dict[str, dict], cols: list[tuple[str, str]]) -> str:
    head = "| | " + " | ".join(c[1] for c in cols) + " |\n|---|" + "---:|" * len(cols) + "\n"
    body = "".join(f"| {name} | " + " | ".join(cell(c[0], r.get(c[0])) for c in cols)
                   + " |\n" for name, r in rows.items())
    return head + body
