"""Stage 6 method from the 11/05 meeting (4안): kernel attraction and repulsion, no training.

Edges the user approved (confirmed or added) attract; edges rejected as unneeded for the purpose repel.
For an untouched edge e:  r(e) = mean_k(e, approved) - mean_k(e, repelled),
k(e, p) = exp(-(1 - s) / tau) * (1 if same relation else REL_MISMATCH), where s is the similarity of the
two file pairs in bge-m3 space (best of both orientations). The score becomes score + gain * r(e).
An edge is hidden when its closest judged edge is a repelled one with k >= margin.
Factual errors ("edge_wrong") are only blocked (stage 7); they do not repel other edges.
"""
from __future__ import annotations

import posixpath

import numpy as np

from ..config import Config
from ..stage3_record import Record
from ..schema import FeedbackEvent, Graph, edge_key
from .base import Correction

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
