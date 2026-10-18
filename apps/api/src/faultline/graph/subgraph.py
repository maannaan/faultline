"""Evidence subgraph for one entity, with status computed at a cutoff.

Every node is returned so a client can keep a stable layout. `visible` says
whether the node existed in memory at the cutoff. Assertion status at the
cutoff comes from `classify_snapshot`, the same rule snapshots use.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from faultline.constants import (
    LABEL_AGENT,
    LABEL_ASSERTION,
    LABEL_ENTITY,
    LABEL_MEMORY_EVENT,
    LABEL_SESSION,
    LABEL_SOURCE,
    REL_ABOUT,
    REL_CONFLICTS_WITH,
    REL_CONTAINS_EVENT,
    REL_RECORDED,
    REL_SUPERSEDES,
    REL_SUPPORTED_BY,
)
from faultline.errors import FaultlineError
from faultline.graph.cypher import as_list, records, run
from faultline.memory.ids import to_iso
from faultline.memory.temporal import (
    TIME_KNOWN,
    TIME_VALID,
    ObservedAssertion,
    classify_snapshot,
)
from faultline.schemas.models import GraphEdge, GraphNode, GraphView


def entity_rows(graph: Any, entity_id: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    entity = records(
        run(
            graph,
            f"""
            MATCH (e:{LABEL_ENTITY} {{id: $entity_id}})
            RETURN e.id AS entity_id, e.canonical_name AS name, e.entity_type AS entity_type
            """,
            {"entity_id": entity_id},
        )
    )
    rows = records(
        run(
            graph,
            f"""
            MATCH (a:{LABEL_ASSERTION})-[:{REL_ABOUT}]->(:{LABEL_ENTITY} {{id: $entity_id}})
            MATCH (a)-[:{REL_SUPPORTED_BY}]->(s:{LABEL_SOURCE})
            OPTIONAL MATCH (ev:{LABEL_MEMORY_EVENT} {{id: a.origin_event_id}})
            OPTIONAL MATCH (se:{LABEL_SESSION})-[:{REL_CONTAINS_EVENT}]->(ev)
            OPTIONAL MATCH (ag:{LABEL_AGENT})-[:{REL_RECORDED}]->(ev)
            RETURN a.id AS assertion_id, a.predicate AS predicate, a.value AS value,
                   a.observed_at AS observed_at, a.valid_from AS valid_from,
                   a.valid_to AS valid_to, a.confidence AS confidence,
                   a.status AS status_now,
                   s.id AS source_id, s.title AS source_title, s.trust_tier AS trust_tier,
                   s.observed_at AS source_observed_at,
                   ev.id AS event_id, se.id AS session_id, ag.id AS agent_id,
                   [(a)-[:{REL_SUPERSEDES}]->(older) | older.id] AS supersedes_ids,
                   [(newer)-[:{REL_SUPERSEDES}]->(a) | newer.id] AS superseded_by_ids,
                   [(a)-[:{REL_CONFLICTS_WITH}]-(other) | other.id] AS conflict_ids
            ORDER BY observed_at, assertion_id
            """,
            {"entity_id": entity_id},
        )
    )
    return (entity[0] if entity else None), rows


def build_graph_view(
    graph: Any,
    *,
    entity_id: str,
    as_of: datetime | None,
    time_mode: str,
    exclude_source_ids: list[str],
) -> GraphView:
    if time_mode not in (TIME_KNOWN, TIME_VALID):
        raise FaultlineError("validation_error", "time_mode must be known or valid", 400)
    entity, rows = entity_rows(graph, entity_id)
    if entity is None:
        raise FaultlineError("not_found", "Entity not found", 404)
    cutoff = to_iso(as_of or datetime.now(UTC))
    excluded = set(exclude_source_ids)
    for row in rows:
        for key in ("supersedes_ids", "superseded_by_ids", "conflict_ids"):
            row[key] = as_list(row.get(key))

    observed = [
        _observed(row)
        for row in rows
        if str(row["observed_at"]) <= cutoff and str(row["source_id"]) not in excluded
    ]
    included, unknown = classify_snapshot(observed, as_of=cutoff, time_mode=time_mode)
    status_at = {member.assertion_id: member.status for member in included}

    nodes: dict[str, GraphNode] = {}
    edges: dict[str, GraphEdge] = {}

    def add_node(node: GraphNode) -> None:
        existing = nodes.get(node.id)
        if existing is None:
            nodes[node.id] = node
        elif node.visible and not existing.visible:
            nodes[node.id] = existing.model_copy(update={"visible": True})

    def add_edge(source: str, target: str, kind: str, visible: bool) -> None:
        key = f"{kind}:{source}->{target}"
        existing = edges.get(key)
        if existing is None or (visible and not existing.visible):
            edges[key] = GraphEdge(id=key, source=source, target=target, type=kind, visible=visible)

    add_node(
        GraphNode(
            id=str(entity["entity_id"]),
            kind="entity",
            label=str(entity.get("name") or entity["entity_id"]),
            sublabel=str(entity.get("entity_type") or ""),
            visible=True,
        )
    )
    for row in rows:
        aid = str(row["assertion_id"])
        visible = aid in status_at
        add_node(
            GraphNode(
                id=aid,
                kind="assertion",
                label=f"{row['predicate']} = {row['value']}",
                sublabel=aid,
                status=status_at.get(aid),
                status_now=_optional(row.get("status_now")),
                observed_at=str(row["observed_at"]),
                excluded=str(row["source_id"]) in excluded,
                visible=visible,
            )
        )
        source_id = str(row["source_id"])
        add_node(
            GraphNode(
                id=source_id,
                kind="source",
                label=str(row.get("source_title") or source_id),
                sublabel=f"{source_id} · {row.get('trust_tier') or 'unknown'}",
                observed_at=_optional(row.get("source_observed_at")),
                excluded=source_id in excluded,
                visible=visible,
            )
        )
        add_edge(aid, source_id, REL_SUPPORTED_BY, visible)
        add_edge(aid, str(entity["entity_id"]), REL_ABOUT, visible)
        event_id = _optional(row.get("event_id"))
        if event_id:
            add_node(
                GraphNode(
                    id=event_id,
                    kind="event",
                    label=event_id,
                    sublabel="MemoryEvent",
                    observed_at=str(row["observed_at"]),
                    visible=visible,
                )
            )
            add_edge(event_id, aid, "CREATED_ASSERTION", visible)
            agent_id = _optional(row.get("agent_id"))
            if agent_id:
                add_node(
                    GraphNode(
                        id=agent_id, kind="agent", label=agent_id, sublabel="Agent", visible=visible
                    )
                )
                add_edge(agent_id, event_id, "RECORDED", visible)
            session_id = _optional(row.get("session_id"))
            if session_id:
                add_node(
                    GraphNode(
                        id=session_id,
                        kind="session",
                        label=session_id,
                        sublabel="Session",
                        visible=visible,
                    )
                )
                add_edge(session_id, event_id, "CONTAINS_EVENT", visible)

    known_ids = {str(row["assertion_id"]) for row in rows}
    for row in rows:
        aid = str(row["assertion_id"])
        for older in row["supersedes_ids"]:
            if older in known_ids:
                add_edge(aid, older, REL_SUPERSEDES, aid in status_at and older in status_at)
        for other in row["conflict_ids"]:
            if other in known_ids and aid < other:
                add_edge(aid, other, REL_CONFLICTS_WITH, aid in status_at and other in status_at)

    moments = sorted({str(row["observed_at"]) for row in rows})
    return GraphView(
        entity_id=str(entity["entity_id"]),
        as_of=cutoff,
        time_mode=time_mode,
        moments=moments,
        validity_unknown_ids=unknown,
        nodes=list(nodes.values()),
        edges=list(edges.values()),
    )


def _observed(row: dict[str, Any]) -> ObservedAssertion:
    return ObservedAssertion(
        assertion_id=str(row["assertion_id"]),
        predicate=str(row["predicate"]),
        value=str(row["value"]),
        observed_at=str(row["observed_at"]),
        valid_from=_optional(row.get("valid_from")),
        valid_to=_optional(row.get("valid_to")),
        confidence=float(row.get("confidence") or 0),
        source_id=str(row["source_id"]),
        event_id=_optional(row.get("event_id")),
        trust_tier=str(row.get("trust_tier") or ""),
        supersedes_ids=tuple(row["supersedes_ids"]),
        superseded_by_ids=tuple(row["superseded_by_ids"]),
        conflict_ids=tuple(row["conflict_ids"]),
    )


def _optional(value: object) -> str | None:
    if value is None or value == "":
        return None
    return str(value)
