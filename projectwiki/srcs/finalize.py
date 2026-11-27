"""Final graph = structure-generation graph + the preference method's proposals + the user's explicit edits.

Explicit edits always win, and they are replayed from the feedback log on every run, so they survive
re-generation after files change. A corrector may rescore any edge but cannot hide imports or links,
which are facts stated in the files; only the user can remove those.
"""
from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from ..config import Config
from ..schema import LEVELS, STRUCTURAL, Edge, FeedbackEvent, Graph, Group, edge_key
if TYPE_CHECKING:
    from ..models.preference import Correction


def finalize(graph: Graph, correction: Correction, feedback: list[FeedbackEvent], cfg: Config) -> Graph:
    g = copy.deepcopy(graph)
    edges = {e.id: e for e in g.edges}
    nodes = {n.id: n for n in g.nodes}
    groups = {gr.id: gr for gr in g.groups}

    # corrector proposals
    for eid, s in correction.edge_scores.items():
        if eid in edges:
            edges[eid].score = s
    hidden = {eid for eid in correction.hide
              if eid in edges and edges[eid].status == "proposed" and edges[eid].reason not in STRUCTURAL}
    for eid in hidden:
        edges[eid].status = "removed_by_corrector"
    for eid, text in correction.explanations.items():
        if eid in edges:
            kept = eid in correction.hide and eid not in hidden
            edges[eid].correction = text + (" — 명시적 참조라 숨기지 않고 점수만 조정" if kept else "")
    for e in correction.new_edges:
        edges.setdefault(e.id, copy.deepcopy(e))
    for nid, gid in correction.node_groups.items():
        if nid in nodes and (gid is None or gid in groups):
            nodes[nid].group = gid

    # explicit edits, in order, so a later event overrides an earlier one
    user_group_by_name = {gr.name: gr.id for gr in groups.values() if gr.origin == "user"}
    for ev in feedback:
        if ev.type.startswith("edge_"):
            key = edge_key(ev.source, ev.target)
            e = edges.get(key)
            if ev.type in ("edge_add", "edge_confirm"):
                # a confirmed edge stays even when a later run does not propose it again
                if e is None:
                    e = edges[key] = Edge(id=key, source=ev.source, target=ev.target, relation=ev.relation or "user",
                                          reason="user", direct=True, score=1.0, origin="user")
                e.status = "confirmed"
                if ev.set_direction:
                    e.source, e.target = ev.source, ev.target
                    e.user_directed = True
                e.label = ev.note or e.label
                if ev.relation and ev.type == "edge_add":
                    e.relation = ev.relation
            elif e is not None:
                e.status = {"edge_confirm": "confirmed", "edge_wrong": "removed_wrong",
                            "edge_irrelevant": "removed_irrelevant"}[ev.type]
        elif ev.type == "group_add" and ev.group and ev.note and ev.group not in groups:
            groups[ev.group] = Group(id=ev.group, name=ev.note, origin="user")
            user_group_by_name[ev.note] = ev.group
        elif ev.type == "group_delete" and ev.group in groups:
            removed = groups.pop(ev.group)
            if user_group_by_name.get(removed.name) == ev.group:
                del user_group_by_name[removed.name]
            for n in nodes.values():
                if n.group == ev.group:
                    n.group = None
        elif ev.type == "node_level" and ev.node in nodes and ev.level in LEVELS:
            nodes[ev.node].level = ev.level
            nodes[ev.node].manual_level = True
        elif ev.type == "node_move" and ev.node in nodes and ev.group:
            gid = ev.group if ev.group in groups else user_group_by_name.get(ev.group)
            if gid is None:  # a new group named by the user
                index = len(user_group_by_name) + 1
                while f"u{index}" in groups:
                    index += 1
                gid = f"u{index}"
                groups[gid] = Group(id=gid, name=ev.group, origin="user")
                user_group_by_name[ev.group] = gid
            nodes[ev.node].group = gid
        elif ev.type == "node_ungroup" and ev.node in nodes:
            nodes[ev.node].group = None

    for e in edges.values():
        if e.status == "proposed" and not e.direct and e.score < cfg.min_score:
            e.status = "removed_low_score"
    for gr in groups.values():
        gr.members = [n.id for n in nodes.values() if n.group == gr.id]
    g.edges = list(edges.values())
    g.groups = list(groups.values())
    return g
