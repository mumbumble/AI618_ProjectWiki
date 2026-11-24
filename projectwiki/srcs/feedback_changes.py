"""Summarize what changed relative to the graph the user just saw."""
from __future__ import annotations

from ..schema import FEEDBACK_TYPES, VISIBLE_STATUS, Edge, FeedbackEvent, Graph, edge_key


def edge_state(edge: Edge | None) -> dict | None:
    if edge is None:
        return None
    return {"visible": edge.status in VISIBLE_STATUS, "status": edge.status,
            "relation": edge.relation, "score": round(edge.score, 4)}


def feedback_changes(before: Graph, after: Graph, events: list[FeedbackEvent], corrector: str) -> dict:
    old_edges = {e.id: e for e in before.edges}
    new_edges = {e.id: e for e in after.edges}
    paths = {node.id: node.path for node in after.nodes}
    touched = {edge_key(ev.source, ev.target): ev for ev in events if ev.type.startswith("edge_")}
    moved = {ev.node: ev for ev in events if ev.type.startswith("node_")}

    def describe_edge(key: str) -> dict:
        old, new = old_edges.get(key), new_edges.get(key)
        edge = new or old
        return {"files": [paths[edge.source], paths[edge.target]], "before": edge_state(old),
                "after": edge_state(new), "reason": new.correction if new else ""}

    direct = []
    for key, event in touched.items():
        row = describe_edge(key)
        old = old_edges.get(key)
        row["action"] = ("관계 이름 수정" if event.type == "edge_add" and old and event.relation
                         and old.relation != event.relation else FEEDBACK_TYPES[event.type])
        direct.append(row)

    old_groups = {group.id: group.name for group in before.groups}
    new_groups = {group.id: group.name for group in after.groups}
    old_membership = {node.id: node.group for node in before.nodes}
    new_membership = {node.id: node.group for node in after.nodes}
    for node, event in moved.items():
        direct.append({"files": [paths[node]], "action": FEEDBACK_TYPES[event.type],
                       "from_group": old_groups.get(old_membership[node], "그룹 없음"),
                       "to_group": new_groups.get(new_membership[node], "그룹 없음")})

    automatic = [describe_edge(key) for key in dict.fromkeys((*old_edges, *new_edges))
                 if key not in touched and edge_state(old_edges.get(key)) != edge_state(new_edges.get(key))]

    def auto_order(change: dict) -> tuple[bool, float]:
        old, new = change["before"] or {}, change["after"] or {}
        return old.get("visible") == new.get("visible"), -abs(new.get("score", 0) - old.get("score", 0))

    automatic.sort(key=auto_order)
    return {"direct": direct, "automatic": automatic, "corrector": corrector, "applied": len(events)}
