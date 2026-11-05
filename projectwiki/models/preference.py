"""Model stage 4 — preference reflection (experimental slot): generalize the user's feedback.

A method is a class built as `Method(cfg)` with `correct(graph, feedback, record) -> Correction`. Explicit edits
(add, confirm, reject, move) are always re-applied afterwards by srcs/finalize.py, so a method only decides what
the feedback implies for edges the user did not touch. Register it in CORRECTORS, or pass
`--corrector package.module:Method`.

- baseline: control condition, feedback is not generalized.
- drift (4안): kernel attraction to approved edges and repulsion from edges rejected as unneeded, no training.
- align (1안): a Bradley–Terry preference model fit on (approved, rejected) pairs.
"""
from __future__ import annotations

import posixpath
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from ..config import Config
from ..schema import Edge, FeedbackEvent, Graph, edge_key
from ..srcs.plugins import load_component
from ..srcs.record import Record
from .clustering import tree_distance


# ---- interface -----------------------------------------------------------------------------------


@dataclass
class Correction:
    edge_scores: dict[str, float] = field(default_factory=dict)  # edge id -> new score
    hide: list[str] = field(default_factory=list)  # edge ids the method drops
    new_edges: list[Edge] = field(default_factory=list)  # edges the method proposes
    node_groups: dict[str, str | None] = field(default_factory=dict)  # file id -> group id it proposes
    explanations: dict[str, str] = field(default_factory=dict)  # edge id -> reason shown to the user
    notes: list[str] = field(default_factory=list)


class Corrector(Protocol):
    name: str

    def correct(self, graph: Graph, feedback: list[FeedbackEvent], record: Record) -> Correction: ...


# ---- baseline ------------------------------------------------------------------------------------


class BaselineCorrector:
    name = "baseline"

    def __init__(self, cfg: Config):
        pass

    def correct(self, graph: Graph, feedback: list[FeedbackEvent], record: Record) -> Correction:
        return Correction(notes=[f"{len(feedback)} feedback events, none generalized"])


# ---- drift (4안) ----------------------------------------------------------------------------------
REL_MISMATCH = 0.7


class DriftCorrector:
    name = "drift"

    def __init__(self, cfg: Config):
        self.tau, self.margin, self.gain = cfg.drift_tau, cfg.drift_margin, cfg.drift_gain

    def correct(self, graph: Graph, feedback: list[FeedbackEvent], record: Record) -> Correction:
        edges = {e.id: e for e in graph.edges}
        judged: dict[str, tuple[str, str, str, str]] = {}  # edge id -> (kind, source, target, relation)
        for ev in feedback:  # later events override earlier ones
            if not ev.type.startswith("edge_"):
                continue
            key = edge_key(ev.source, ev.target)
            rel = ev.relation or (edges[key].relation if key in edges else "user")
            kind = {"edge_confirm": "approve", "edge_add": "approve", "edge_irrelevant": "repel"}.get(ev.type, "block")
            judged[key] = (kind, ev.source, ev.target, rel)
        approved = [v for v in judged.values() if v[0] == "approve"]
        repelled = [v for v in judged.values() if v[0] == "repel"]
        out = Correction(notes=[f"{len(approved)} approved, {len(repelled)} repelled edges as kernel centres"])
        if not approved and not repelled:
            return out

        f = record.file_emb
        idx = record.file_index
        name = {n.id: posixpath.basename(n.path) for n in graph.nodes}

        def kernel(e, p) -> float:
            a1, b1, a2, b2 = f[idx[e.source]], f[idx[e.target]], f[idx[p[1]]], f[idx[p[2]]]
            s = max((a1 @ a2 + b1 @ b2) / 2, (a1 @ b2 + b1 @ a2) / 2)
            return float(np.exp(-(1.0 - s) / self.tau)) * (1.0 if e.relation == p[3] else REL_MISMATCH)

        for e in graph.edges:
            if e.id in judged or e.status != "proposed":
                continue
            ka = [kernel(e, p) for p in approved]
            kr = [kernel(e, p) for p in repelled]
            r = (np.mean(ka) if ka else 0.0) - (np.mean(kr) if kr else 0.0)
            out.edge_scores[e.id] = e.score + self.gain * float(r)
            best_a = max(range(len(ka)), key=ka.__getitem__) if ka else None
            best_r = max(range(len(kr)), key=kr.__getitem__) if kr else None
            top_a = ka[best_a] if ka else 0.0
            top_r = kr[best_r] if kr else 0.0
            if top_r >= self.margin and top_r > top_a:
                p = repelled[best_r]
                out.hide.append(e.id)
                out.explanations[e.id] = f"목적상 불필요로 거절한 '{name[p[1]]} – {name[p[2]]}'와 비슷함 (k={top_r:.2f})"
            elif top_a >= self.margin:
                p = approved[best_a]
                out.explanations[e.id] = f"승인한 '{name[p[1]]} – {name[p[2]]}'와 비슷함 (k={top_a:.2f})"
        out.notes.append(f"{len(out.hide)} edges hidden, {len(out.explanations) - len(out.hide)} reinforced")
        return out


# ---- align (1안) ----------------------------------------------------------------------------------
PCA_DIMS = 16
STEPS, LR = 300, 0.5


class AlignCorrector:
    name = "align"

    def __init__(self, cfg: Config):
        self.l2 = cfg.align_l2

    def features(self, edges: list[Edge], record: Record, group_of: dict) -> np.ndarray:
        f, idx = record.file_emb, record.file_index
        a = np.stack([f[idx[e.source]] for e in edges])
        b = np.stack([f[idx[e.target]] for e in edges])
        pair = a * b
        pair -= pair.mean(0)
        k = max(1, min(PCA_DIMS, len(edges) - 1))
        pair = pair @ np.linalg.svd(pair, full_matrices=False)[2][:k].T
        paths = record.file_by_id
        extra = np.array([[float((a[i] * b[i]).sum()),
                           float(tree_distance([paths[e.source].path, paths[e.target].path])[0, 1]),
                           float(group_of.get(e.source) is not None and group_of.get(e.source) == group_of.get(e.target))]
                          for i, e in enumerate(edges)])
        x = np.hstack([pair, extra])
        return (x - x.mean(0)) / (x.std(0) + 1e-6)

    def correct(self, graph: Graph, feedback: list[FeedbackEvent], record: Record) -> Correction:
        edges = {e.id: e for e in graph.edges}
        label: dict[str, int] = {}  # edge id -> 1 approved / 0 rejected; later events win
        for ev in feedback:
            if not ev.type.startswith("edge_"):
                continue
            key = edge_key(ev.source, ev.target)
            label[key] = 1 if ev.type in ("edge_confirm", "edge_add") else 0
            if key not in edges and ev.type in ("edge_add", "edge_confirm"):  # user-asserted edges need features too
                edges[key] = Edge(id=key, source=ev.source, target=ev.target, relation=ev.relation or "user",
                                  reason="user", direct=True, score=1.0, origin="user")
        pos = [k for k, v in label.items() if v == 1 and k in edges]
        neg = [k for k, v in label.items() if v == 0 and k in edges]
        if not pos or not neg:
            return Correction(notes=["align needs at least one approved and one rejected edge"])

        group_of = {n.id: n.group for n in graph.nodes}
        order = list(edges)
        row = {k: i for i, k in enumerate(order)}
        x = self.features([edges[k] for k in order], record, group_of)
        diff = np.stack([x[row[a]] - x[row[r]] for a in pos for r in neg])
        w = np.zeros(x.shape[1])
        for _ in range(STEPS):  # gradient descent on the Bradley–Terry loss
            p = 1.0 / (1.0 + np.exp(-(diff @ w)))
            w -= LR * (-(diff * (1.0 - p)[:, None]).mean(0) + self.l2 * w)
        s = x @ w
        acc = float(((diff @ w) > 0).mean())
        s_pos, s_neg = s[[row[k] for k in pos]], s[[row[k] for k in neg]]
        mid, scale = (s_pos.mean() + s_neg.mean()) / 2, max(s_pos.mean() - s_neg.mean(), 1e-6) / 4

        out = Correction(notes=[f"Bradley–Terry fit on {len(pos)} approved x {len(neg)} rejected = {len(diff)} pairs, "
                                f"train pair accuracy {acc:.2f}"])
        for e in graph.edges:
            if e.id in label or e.status != "proposed":
                continue
            v = s[row[e.id]]
            prob = float(1.0 / (1.0 + np.exp(-(v - mid) / scale)))
            out.edge_scores[e.id] = prob
            if v < s_neg.min():
                out.hide.append(e.id)
                out.explanations[e.id] = f"선호 모델: 거절한 어떤 연결보다 점수가 낮음 (p={prob:.2f}, 승인 {len(pos)}·거절 {len(neg)}로 학습)"
            elif v > s_pos.mean():
                out.explanations[e.id] = f"선호 모델: 승인한 연결 평균보다 점수가 높음 (p={prob:.2f})"
        out.notes.append(f"{len(out.hide)} edges hidden, {len(out.explanations) - len(out.hide)} reinforced")
        return out


# ---- registry ------------------------------------------------------------------------------------
CORRECTORS = {"baseline": BaselineCorrector, "drift": DriftCorrector, "align": AlignCorrector}


def get_corrector(name: str, cfg: Config) -> Corrector:
    return load_component(name, CORRECTORS, cfg)
