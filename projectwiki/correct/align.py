"""Stage 6 method from the 11/05 meeting (1안): preference alignment on the user's feedback.

Approved edges (confirmed or added) should score above rejected ones (wrong or unneeded for the purpose).
A Bradley–Terry model s(e) = w·φ(e) is fit on every (approved, rejected) pair with
    loss = mean(-log σ(s(a) - s(r))) + l2/2 · ‖w‖²
and then rescores the edges the user did not touch.

φ(e) uses only the content and place of the two files, so a user-added edge and an AI edge are described
the same way: bge-m3 pair features (elementwise product of the two file vectors, reduced by PCA), their
cosine similarity, folder-tree distance, and whether both share a group. Columns are standardized.

An untouched edge is hidden only when it scores below every rejected edge, and reinforced when it scores
above the average approved edge. Its new score is a probability calibrated so that the mean rejected
edge maps to about 0.12 and the mean approved edge to about 0.88.
"""
from __future__ import annotations

import numpy as np

from ..cluster.baseline import tree_distance
from ..config import Config
from ..record import Record
from ..schema import Edge, FeedbackEvent, Graph, edge_key
from .base import Correction

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
            if key not in edges and ev.type == "edge_add":  # a user-added edge needs features too
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
