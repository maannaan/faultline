"""Cypher reads and writes. Values stay in parameters."""

from __future__ import annotations

from typing import Any

from faultline.constants import (
    LABEL_AGENT,
    LABEL_ANSWER_CLAIM,
    LABEL_ASSERTION,
    LABEL_ENTITY,
    LABEL_HANDOFF,
    LABEL_MEMORY_EVENT,
    LABEL_REPLAY_RUN,
    LABEL_SESSION,
    LABEL_SNAPSHOT,
    LABEL_SOURCE,
    LABEL_TASK,
    LABEL_TENANT,
    LABEL_USER,
    REL_ABOUT,
    REL_ASSIGNED_TO,
    REL_CONFLICTS_WITH,
    REL_CONTAINS_EVENT,
    REL_CREATED_ASSERTION,
    REL_HAS_AGENT,
    REL_HAS_HANDOFF,
    REL_HAS_USER,
    REL_INCLUDES_ASSERTION,
    REL_INCLUDES_CONFLICT,
    REL_MENTIONS_ENTITY,
    REL_OBSERVED_SOURCE,
    REL_OWNS_TASK,
    REL_PRODUCED_ANSWER,
    REL_RECORDED,
    REL_REFERENCES_MEMORY,
    REL_STARTED_SESSION,
    REL_SUPERSEDES,
    REL_SUPPORTED_BY,
    REL_SUPPORTED_BY_ASSERTION,
    REL_USED_EVIDENCE,
    REL_USED_SNAPSHOT,
    STATUS_DISPUTED,
    STATUS_SUPERSEDED,
)
from faultline.graph.cypher import as_list, records, run


def _clean(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    cleaned: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, str) and value == "null":
            cleaned[key] = None
        else:
            cleaned[key] = value
    return cleaned


def ensure_user(graph: Any, tenant_id: str, user_id: str) -> None:
    run(
        graph,
        f"""
        MATCH (t:{LABEL_TENANT} {{id: $tenant_id}})
        MERGE (u:{LABEL_USER} {{id: $user_id}})
        SET u.tenant_id = $tenant_id
        MERGE (t)-[:{REL_HAS_USER}]->(u)
        """,
        {"tenant_id": tenant_id, "user_id": user_id},
    )


def ensure_agent(graph: Any, tenant_id: str, agent_id: str, role: str, version: str) -> None:
    run(
        graph,
        f"""
        MATCH (t:{LABEL_TENANT} {{id: $tenant_id}})
        MERGE (ag:{LABEL_AGENT} {{id: $agent_id}})
        SET ag.role = $role, ag.version = $version, ag.tenant_id = $tenant_id
        MERGE (t)-[:{REL_HAS_AGENT}]->(ag)
        """,
        {
            "tenant_id": tenant_id,
            "agent_id": agent_id,
            "role": role,
            "version": version,
        },
    )


def ensure_session(graph: Any, user_id: str, session_id: str, started_at: str) -> bool:
    result = records(
        run(
            graph,
            f"""
            MATCH (u:{LABEL_USER} {{id: $user_id}})
            MERGE (se:{LABEL_SESSION} {{id: $session_id}})
            ON CREATE SET se.started_at = $started_at
            MERGE (u)-[:{REL_STARTED_SESSION}]->(se)
            RETURN se.id AS session_id
            """,
            {"user_id": user_id, "session_id": session_id, "started_at": started_at},
        )
    )
    return bool(result)


def find_session(graph: Any, session_id: str) -> bool:
    return bool(
        records(
            run(
                graph,
                f"MATCH (se:{LABEL_SESSION} {{id: $session_id}}) RETURN se.id AS session_id",
                {"session_id": session_id},
            )
        )
    )


def find_agent(graph: Any, agent_id: str) -> bool:
    return bool(
        records(
            run(
                graph,
                f"MATCH (ag:{LABEL_AGENT} {{id: $agent_id}}) RETURN ag.id AS agent_id",
                {"agent_id": agent_id},
            )
        )
    )


def find_event_by_idempotency(graph: Any, idempotency_key: str) -> dict[str, Any] | None:
    found = records(
        run(
            graph,
            f"""
            MATCH (ev:{LABEL_MEMORY_EVENT} {{idempotency_key: $idempotency_key}})
            RETURN ev.id AS event_id, ev.event_type AS event_type,
                   ev.observed_at AS observed_at, ev.idempotency_key AS idempotency_key
            """,
            {"idempotency_key": idempotency_key},
        )
    )
    return _clean(found[0]) if found else None


def insert_event(
    graph: Any,
    *,
    event_id: str,
    event_type: str,
    observed_at: str,
    idempotency_key: str,
    session_id: str,
    agent_id: str,
) -> dict[str, Any] | None:
    found = records(
        run(
            graph,
            f"""
            MATCH (se:{LABEL_SESSION} {{id: $session_id}})
            MATCH (ag:{LABEL_AGENT} {{id: $agent_id}})
            CREATE (ev:{LABEL_MEMORY_EVENT})
            SET ev.id = $event_id, ev.event_type = $event_type,
                ev.observed_at = $observed_at, ev.idempotency_key = $idempotency_key
            CREATE (se)-[:{REL_CONTAINS_EVENT}]->(ev)
            CREATE (ag)-[:{REL_RECORDED}]->(ev)
            RETURN ev.id AS event_id, ev.event_type AS event_type,
                   ev.observed_at AS observed_at, ev.idempotency_key AS idempotency_key
            """,
            {
                "session_id": session_id,
                "agent_id": agent_id,
                "event_id": event_id,
                "event_type": event_type,
                "observed_at": observed_at,
                "idempotency_key": idempotency_key,
            },
        )
    )
    return _clean(found[0]) if found else None


def find_source(graph: Any, source_id: str) -> dict[str, Any] | None:
    found = records(
        run(
            graph,
            f"""
            MATCH (s:{LABEL_SOURCE} {{id: $source_id}})
            RETURN s.id AS source_id, s.trust_tier AS trust_tier,
                   s.content_hash AS content_hash, s.origin_event_id AS event_id
            """,
            {"source_id": source_id},
        )
    )
    return _clean(found[0]) if found else None


def insert_source(
    graph: Any,
    *,
    source_id: str,
    source_type: str,
    trust_tier: str,
    observed_at: str,
    title: str,
    excerpt: str,
    content_hash: str,
    event_id: str,
    event_idempotency_key: str,
    session_id: str,
    agent_id: str,
) -> dict[str, Any] | None:
    found = records(
        run(
            graph,
            f"""
            MATCH (se:{LABEL_SESSION} {{id: $session_id}})
            MATCH (ag:{LABEL_AGENT} {{id: $agent_id}})
            CREATE (s:{LABEL_SOURCE})
            SET s.id = $source_id, s.source_type = $source_type, s.trust_tier = $trust_tier,
                s.observed_at = $observed_at, s.title = $title, s.excerpt = $excerpt,
                s.content_hash = $content_hash, s.origin_event_id = $event_id
            CREATE (ev:{LABEL_MEMORY_EVENT})
            SET ev.id = $event_id, ev.event_type = 'source_recorded',
                ev.observed_at = $observed_at, ev.idempotency_key = $event_idempotency_key
            CREATE (ev)-[:{REL_OBSERVED_SOURCE}]->(s)
            CREATE (se)-[:{REL_CONTAINS_EVENT}]->(ev)
            CREATE (ag)-[:{REL_RECORDED}]->(ev)
            RETURN s.id AS source_id, s.trust_tier AS trust_tier,
                   s.content_hash AS content_hash, s.origin_event_id AS event_id
            """,
            {
                "session_id": session_id,
                "agent_id": agent_id,
                "source_id": source_id,
                "source_type": source_type,
                "trust_tier": trust_tier,
                "observed_at": observed_at,
                "title": title,
                "excerpt": excerpt,
                "content_hash": content_hash,
                "event_id": event_id,
                "event_idempotency_key": event_idempotency_key,
            },
        )
    )
    return _clean(found[0]) if found else None


def find_entity(graph: Any, entity_id: str) -> dict[str, Any] | None:
    found = records(
        run(
            graph,
            f"""
            MATCH (e:{LABEL_ENTITY} {{id: $entity_id}})
            RETURN e.id AS id, e.entity_type AS entity_type,
                   e.canonical_name AS canonical_name, e.normalized_name AS normalized_name,
                   e.normalized_type AS normalized_type
            """,
            {"entity_id": entity_id},
        )
    )
    return _clean(found[0]) if found else None


def merge_entity(
    graph: Any,
    *,
    entity_id: str,
    canonical_name: str,
    entity_type: str,
    normalized_name: str,
    normalized_type: str,
) -> dict[str, Any]:
    found = records(
        run(
            graph,
            f"""
            MERGE (e:{LABEL_ENTITY} {{
                normalized_name: $normalized_name,
                normalized_type: $normalized_type
            }})
            ON CREATE SET e.id = $entity_id, e.canonical_name = $canonical_name,
                          e.entity_type = $entity_type
            RETURN e.id AS id, e.entity_type AS entity_type,
                   e.canonical_name AS canonical_name, e.normalized_name AS normalized_name,
                   e.normalized_type AS normalized_type
            """,
            {
                "entity_id": entity_id,
                "canonical_name": canonical_name,
                "entity_type": entity_type,
                "normalized_name": normalized_name,
                "normalized_type": normalized_type,
            },
        )
    )
    if not found:
        raise RuntimeError("Entity merge returned no row")
    row = _clean(found[0])
    assert row is not None
    return row


def list_entities(graph: Any) -> list[dict[str, Any]]:
    return records(
        run(
            graph,
            f"""
            MATCH (e:{LABEL_ENTITY})
            RETURN e.id AS entity_id, e.entity_type AS entity_type,
                   e.canonical_name AS canonical_name
            ORDER BY canonical_name
            """,
        )
    )


def find_assertion_by_idempotency(graph: Any, idempotency_key: str) -> str | None:
    found = records(
        run(
            graph,
            f"""
            MATCH (a:{LABEL_ASSERTION} {{idempotency_key: $idempotency_key}})
            RETURN a.id AS assertion_id
            """,
            {"idempotency_key": idempotency_key},
        )
    )
    if not found:
        return None
    return str(found[0]["assertion_id"])


def find_assertion_brief(graph: Any, assertion_id: str) -> dict[str, Any] | None:
    found = records(
        run(
            graph,
            f"""
            MATCH (a:{LABEL_ASSERTION} {{id: $assertion_id}})-[:{REL_ABOUT}]->(e:{LABEL_ENTITY})
            RETURN a.id AS assertion_id, a.predicate AS predicate, e.id AS entity_id
            """,
            {"assertion_id": assertion_id},
        )
    )
    return _clean(found[0]) if found else None


def find_semantic_duplicate(
    graph: Any,
    *,
    entity_id: str,
    predicate: str,
    value_normalized: str,
    source_id: str,
) -> str | None:
    found = records(
        run(
            graph,
            f"""
            MATCH (a:{LABEL_ASSERTION} {{
                predicate: $predicate,
                value_normalized: $value_normalized
            }})-[:{REL_ABOUT}]->(e:{LABEL_ENTITY} {{id: $entity_id}})
            MATCH (a)-[:{REL_SUPPORTED_BY}]->(s:{LABEL_SOURCE} {{id: $source_id}})
            RETURN a.id AS assertion_id
            """,
            {
                "predicate": predicate,
                "value_normalized": value_normalized,
                "entity_id": entity_id,
                "source_id": source_id,
            },
        )
    )
    if not found:
        return None
    return str(found[0]["assertion_id"])


def list_active_claims(graph: Any, entity_id: str, predicate: str) -> list[dict[str, Any]]:
    return records(
        run(
            graph,
            f"""
            MATCH (a:{LABEL_ASSERTION} {{predicate: $predicate}})-[:{REL_ABOUT}]->
                  (e:{LABEL_ENTITY} {{id: $entity_id}})
            WHERE a.status = 'current' OR a.status = 'disputed'
            MATCH (a)-[:{REL_SUPPORTED_BY}]->(s:{LABEL_SOURCE})
            RETURN a.id AS assertion_id, a.value_normalized AS value_normalized,
                   a.status AS status, s.trust_tier AS trust_tier
            """,
            {"predicate": predicate, "entity_id": entity_id},
        )
    )


def insert_assertion(graph: Any, fields: dict[str, Any]) -> str | None:
    assignments = [
        "a.id = $id",
        "a.predicate = $predicate",
        "a.value = $value",
        "a.value_normalized = $value_normalized",
        "a.status = $status",
        "a.observed_at = $observed_at",
        "a.confidence = $confidence",
        "a.policy_version = $policy_version",
        "a.resolution = $resolution",
        "a.resolution_reason = $resolution_reason",
        "a.idempotency_key = $idempotency_key",
        "a.origin_event_id = $origin_event_id",
    ]
    params = dict(fields)
    if fields.get("valid_from"):
        assignments.append("a.valid_from = $valid_from")
    else:
        params.pop("valid_from", None)
    if fields.get("valid_to"):
        assignments.append("a.valid_to = $valid_to")
    else:
        params.pop("valid_to", None)
    set_clause = ", ".join(assignments)
    found = records(
        run(
            graph,
            f"""
            MATCH (e:{LABEL_ENTITY} {{id: $entity_id}})
            MATCH (s:{LABEL_SOURCE} {{id: $source_id}})
            MATCH (se:{LABEL_SESSION} {{id: $session_id}})
            MATCH (ag:{LABEL_AGENT} {{id: $agent_id}})
            CREATE (a:{LABEL_ASSERTION})
            SET {set_clause}
            CREATE (a)-[:{REL_ABOUT}]->(e)
            CREATE (a)-[:{REL_SUPPORTED_BY}]->(s)
            CREATE (ev:{LABEL_MEMORY_EVENT})
            SET ev.id = $origin_event_id, ev.event_type = 'assertion_recorded',
                ev.observed_at = $observed_at, ev.idempotency_key = $event_idempotency_key
            CREATE (ev)-[:{REL_CREATED_ASSERTION}]->(a)
            CREATE (ev)-[:{REL_OBSERVED_SOURCE}]->(s)
            CREATE (ev)-[:{REL_MENTIONS_ENTITY}]->(e)
            CREATE (se)-[:{REL_CONTAINS_EVENT}]->(ev)
            CREATE (ag)-[:{REL_RECORDED}]->(ev)
            RETURN a.id AS assertion_id
            """,
            params,
        )
    )
    if not found:
        return None
    return str(found[0]["assertion_id"])


def link_duplicate_event(
    graph: Any,
    *,
    assertion_id: str,
    source_id: str,
    entity_id: str,
    event_id: str,
    observed_at: str,
    idempotency_key: str,
    session_id: str,
    agent_id: str,
) -> bool:
    found = records(
        run(
            graph,
            f"""
            MATCH (a:{LABEL_ASSERTION} {{id: $assertion_id}})
            MATCH (s:{LABEL_SOURCE} {{id: $source_id}})
            MATCH (e:{LABEL_ENTITY} {{id: $entity_id}})
            MATCH (se:{LABEL_SESSION} {{id: $session_id}})
            MATCH (ag:{LABEL_AGENT} {{id: $agent_id}})
            CREATE (ev:{LABEL_MEMORY_EVENT})
            SET ev.id = $event_id, ev.event_type = 'assertion_recorded',
                ev.observed_at = $observed_at, ev.idempotency_key = $idempotency_key
            CREATE (ev)-[:{REL_CREATED_ASSERTION}]->(a)
            CREATE (ev)-[:{REL_OBSERVED_SOURCE}]->(s)
            CREATE (ev)-[:{REL_MENTIONS_ENTITY}]->(e)
            CREATE (se)-[:{REL_CONTAINS_EVENT}]->(ev)
            CREATE (ag)-[:{REL_RECORDED}]->(ev)
            RETURN ev.id AS event_id
            """,
            {
                "assertion_id": assertion_id,
                "source_id": source_id,
                "entity_id": entity_id,
                "session_id": session_id,
                "agent_id": agent_id,
                "event_id": event_id,
                "observed_at": observed_at,
                "idempotency_key": idempotency_key,
            },
        )
    )
    return bool(found)


def supersede(graph: Any, newer_id: str, older_id: str, reason: str) -> None:
    run(
        graph,
        f"""
        MATCH (newer:{LABEL_ASSERTION} {{id: $newer_id}})
        MATCH (older:{LABEL_ASSERTION} {{id: $older_id}})
        SET older.status = $status, older.resolution = $resolution,
            older.resolution_reason = $reason
        MERGE (newer)-[:{REL_SUPERSEDES}]->(older)
        """,
        {
            "newer_id": newer_id,
            "older_id": older_id,
            "status": STATUS_SUPERSEDED,
            "resolution": STATUS_SUPERSEDED,
            "reason": reason,
        },
    )


def dispute(graph: Any, newer_id: str, older_id: str, reason: str) -> None:
    run(
        graph,
        f"""
        MATCH (newer:{LABEL_ASSERTION} {{id: $newer_id}})
        MATCH (older:{LABEL_ASSERTION} {{id: $older_id}})
        SET older.status = $status, older.resolution = $resolution,
            older.resolution_reason = $reason
        MERGE (newer)-[:{REL_CONFLICTS_WITH}]->(older)
        """,
        {
            "newer_id": newer_id,
            "older_id": older_id,
            "status": STATUS_DISPUTED,
            "resolution": "unresolved_equal_trust",
            "reason": reason,
        },
    )


def assertion_view(graph: Any, assertion_id: str) -> dict[str, Any] | None:
    found = records(
        run(
            graph,
            f"""
            MATCH (a:{LABEL_ASSERTION} {{id: $assertion_id}})-[:{REL_ABOUT}]->(e:{LABEL_ENTITY})
            OPTIONAL MATCH (a)-[:{REL_SUPPORTED_BY}]->(s:{LABEL_SOURCE})
            OPTIONAL MATCH (a)-[:{REL_SUPERSEDES}]->(old:{LABEL_ASSERTION})
            RETURN a.id AS assertion_id, a.status AS status, a.policy_version AS policy_version,
                   a.resolution AS resolution, s.id AS source_id, e.id AS entity_id,
                   collect(DISTINCT old.id) AS superseded_ids
            """,
            {"assertion_id": assertion_id},
        )
    )
    if not found or not found[0].get("assertion_id"):
        return None
    row = found[0]
    row["superseded_ids"] = as_list(row.get("superseded_ids"))
    return row


def entity_exists(graph: Any, entity_id: str) -> bool:
    return find_entity(graph, entity_id) is not None


def timeline_rows(graph: Any, entity_id: str, limit: int) -> list[dict[str, Any]]:
    found = records(
        run(
            graph,
            f"""
            MATCH (e:{LABEL_ENTITY} {{id: $entity_id}})
            MATCH (a:{LABEL_ASSERTION})-[:{REL_ABOUT}]->(e)
            WITH a
            ORDER BY a.observed_at
            LIMIT $limit
            OPTIONAL MATCH (a)-[:{REL_SUPPORTED_BY}]->(s:{LABEL_SOURCE})
            OPTIONAL MATCH (a)-[:{REL_SUPERSEDES}]->(old:{LABEL_ASSERTION})
            OPTIONAL MATCH (a)-[:{REL_CONFLICTS_WITH}]-(other:{LABEL_ASSERTION})
            RETURN a.id AS assertion_id, a.predicate AS predicate, a.value AS value,
                   a.status AS status, a.observed_at AS observed_at,
                   a.valid_from AS valid_from, a.valid_to AS valid_to,
                   a.confidence AS confidence, a.resolution AS resolution,
                   a.resolution_reason AS resolution_reason,
                   a.policy_version AS policy_version, a.origin_event_id AS event_id,
                   s.id AS source_id,
                   collect(DISTINCT old.id) AS supersedes_ids,
                   collect(DISTINCT other.id) AS conflicts_with_ids
            ORDER BY observed_at
            """,
            {"entity_id": entity_id, "limit": limit},
        )
    )
    rows: list[dict[str, Any]] = []
    for row in found:
        if not row.get("assertion_id"):
            continue
        row["supersedes_ids"] = as_list(row.get("supersedes_ids"))
        row["conflicts_with_ids"] = as_list(row.get("conflicts_with_ids"))
        rows.append(row)
    return rows


def observed_assertions(graph: Any, as_of: str) -> list[dict[str, Any]]:
    return _observed_rows(graph, "WHERE a.observed_at <= $as_of", {"as_of": as_of})


def observed_assertions_for_entity(graph: Any, entity_id: str, as_of: str) -> list[dict[str, Any]]:
    """Same rows as observed_assertions, for one entity, matched through the Entity id index."""
    return _observed_rows(
        graph,
        "WHERE e.id = $entity_id AND a.observed_at <= $as_of",
        {"entity_id": entity_id, "as_of": as_of},
    )


def _observed_rows(graph: Any, where: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    found = records(
        run(
            graph,
            f"""
            MATCH (a:{LABEL_ASSERTION})-[:{REL_ABOUT}]->(e:{LABEL_ENTITY})
            {where}
            MATCH (a)-[:{REL_SUPPORTED_BY}]->(s:{LABEL_SOURCE})
            RETURN a.id AS assertion_id, a.predicate AS predicate, a.value AS value,
                   a.observed_at AS observed_at, a.valid_from AS valid_from,
                   a.valid_to AS valid_to, a.confidence AS confidence,
                   a.origin_event_id AS event_id, s.id AS source_id,
                   s.trust_tier AS trust_tier, e.id AS entity_id,
                   [(a)-[:{REL_SUPERSEDES}]->(older) | older.id] AS supersedes_ids,
                   [(newer)-[:{REL_SUPERSEDES}]->(a) | newer.id] AS superseded_by_ids,
                   [(a)-[:{REL_CONFLICTS_WITH}]-(other) | other.id] AS conflict_ids
            ORDER BY observed_at
            """,
            params,
        )
    )
    rows: list[dict[str, Any]] = []
    for row in found:
        if not row.get("assertion_id"):
            continue
        row["supersedes_ids"] = as_list(row.get("supersedes_ids"))
        row["superseded_by_ids"] = as_list(row.get("superseded_by_ids"))
        row["conflict_ids"] = as_list(row.get("conflict_ids"))
        rows.append(row)
    return rows


def find_snapshot_id_by_idempotency(graph: Any, idempotency_key: str) -> str | None:
    found = records(
        run(
            graph,
            f"""
            MATCH (s:{LABEL_SNAPSHOT} {{idempotency_key: $idempotency_key}})
            RETURN s.id AS snapshot_id
            """,
            {"idempotency_key": idempotency_key},
        )
    )
    if not found or not found[0].get("snapshot_id"):
        return None
    return str(found[0]["snapshot_id"])


def insert_snapshot(graph: Any, fields: dict[str, Any], members: list[dict[str, Any]]) -> None:
    run(
        graph,
        f"""
        CREATE (s:{LABEL_SNAPSHOT})
        SET s.id = $id, s.as_of_time = $as_of_time, s.time_mode = $time_mode,
            s.policy_version = $policy_version, s.predicate = $predicate,
            s.exclude_source_ids = $exclude_source_ids,
            s.validity_unknown_ids = $validity_unknown_ids,
            s.idempotency_key = $idempotency_key, s.created_at = $created_at
        """,
        fields,
    )
    for entity_id in fields["entity_ids"]:
        run(
            graph,
            f"""
            MATCH (s:{LABEL_SNAPSHOT} {{id: $snapshot_id}})
            MATCH (e:{LABEL_ENTITY} {{id: $entity_id}})
            CREATE (s)-[:{REL_ABOUT}]->(e)
            """,
            {"snapshot_id": fields["id"], "entity_id": entity_id},
        )
    for member in members:
        run(
            graph,
            f"""
            MATCH (s:{LABEL_SNAPSHOT} {{id: $snapshot_id}})
            MATCH (a:{LABEL_ASSERTION} {{id: $assertion_id}})
            CREATE (s)-[edge:{REL_INCLUDES_ASSERTION}]->(a)
            SET edge.status_at_snapshot = $status, edge.reason = $reason,
                edge.supersedes_ids = $supersedes_ids,
                edge.conflicts_with_ids = $conflicts_with_ids
            """,
            {"snapshot_id": fields["id"], **member},
        )


def load_snapshot(graph: Any, snapshot_id: str) -> dict[str, Any] | None:
    found = records(
        run(
            graph,
            f"""
            MATCH (s:{LABEL_SNAPSHOT} {{id: $snapshot_id}})
            OPTIONAL MATCH (s)-[edge:{REL_INCLUDES_ASSERTION}]->(a:{LABEL_ASSERTION})
            OPTIONAL MATCH (a)-[:{REL_SUPPORTED_BY}]->(src:{LABEL_SOURCE})
            RETURN s.id AS snapshot_id, s.as_of_time AS as_of_time, s.time_mode AS time_mode,
                   s.policy_version AS policy_version, s.predicate AS predicate,
                   s.exclude_source_ids AS exclude_source_ids,
                   s.validity_unknown_ids AS validity_unknown_ids,
                   s.idempotency_key AS idempotency_key,
                   a.id AS assertion_id, a.predicate AS assertion_predicate, a.value AS value,
                   a.observed_at AS observed_at, a.valid_from AS valid_from,
                   a.valid_to AS valid_to, a.confidence AS confidence,
                   a.origin_event_id AS event_id, src.id AS source_id,
                   edge.status_at_snapshot AS status, edge.reason AS reason,
                   edge.supersedes_ids AS supersedes_ids,
                   edge.conflicts_with_ids AS conflicts_with_ids
            """,
            {"snapshot_id": snapshot_id},
        )
    )
    if not found or not found[0].get("snapshot_id"):
        return None
    return {"rows": found}


def evidence_path(graph: Any, assertion_id: str) -> dict[str, Any] | None:
    found = records(
        run(
            graph,
            f"""
            MATCH (a:{LABEL_ASSERTION} {{id: $assertion_id}})-[:{REL_ABOUT}]->(e:{LABEL_ENTITY})
            OPTIONAL MATCH (a)-[:{REL_SUPPORTED_BY}]->(s:{LABEL_SOURCE})
            OPTIONAL MATCH (ev:{LABEL_MEMORY_EVENT} {{id: a.origin_event_id}})
            OPTIONAL MATCH (se:{LABEL_SESSION})-[:{REL_CONTAINS_EVENT}]->(ev)
            RETURN a.id AS assertion_id, a.status AS status, s.id AS source_id,
                   ev.id AS event_id, se.id AS session_id, e.id AS entity_id,
                   [(a)-[:{REL_SUPERSEDES}]->(older) | older.id] AS supersedes_ids,
                   [(a)-[:{REL_CONFLICTS_WITH}]-(other) | other.id] AS conflicts_with_ids
            """,
            {"assertion_id": assertion_id},
        )
    )
    if not found or not found[0].get("assertion_id"):
        return None
    row = found[0]
    row["supersedes_ids"] = as_list(row.get("supersedes_ids"))
    row["conflicts_with_ids"] = as_list(row.get("conflicts_with_ids"))
    return row


def find_replay_id_by_idempotency(graph: Any, idempotency_key: str) -> str | None:
    found = records(
        run(
            graph,
            f"""
            MATCH (r:{LABEL_REPLAY_RUN} {{idempotency_key: $idempotency_key}})
            RETURN r.id AS replay_id
            """,
            {"idempotency_key": idempotency_key},
        )
    )
    if not found or not found[0].get("replay_id"):
        return None
    return str(found[0]["replay_id"])


def insert_replay(graph: Any, fields: dict[str, Any], claims: list[dict[str, Any]]) -> None:
    run(
        graph,
        f"""
        MATCH (s:{LABEL_SNAPSHOT} {{id: $snapshot_id}})
        CREATE (r:{LABEL_REPLAY_RUN})
        SET r.id = $id, r.question = $question, r.predicate = $predicate,
            r.policy_version = $policy_version, r.prompt_version = $prompt_version,
            r.model_version = $model_version, r.idempotency_key = $idempotency_key,
            r.created_at = $created_at, r.citation_rejected = $citation_rejected,
            r.snapshot_id = $snapshot_id
        CREATE (r)-[:{REL_USED_SNAPSHOT}]->(s)
        """,
        fields,
    )
    evidence_ids = list(dict.fromkeys(fields["evidence_ids"]))
    for evidence_id in evidence_ids:
        run(
            graph,
            f"""
            MATCH (r:{LABEL_REPLAY_RUN} {{id: $replay_id}})
            MATCH (a:{LABEL_ASSERTION} {{id: $assertion_id}})
            CREATE (r)-[:{REL_USED_EVIDENCE}]->(a)
            """,
            {"replay_id": fields["id"], "assertion_id": evidence_id},
        )
    for claim in claims:
        run(
            graph,
            f"""
            MATCH (r:{LABEL_REPLAY_RUN} {{id: $replay_id}})
            CREATE (c:{LABEL_ANSWER_CLAIM})
            SET c.id = $claim_id, c.predicate = $predicate, c.value = $value,
                c.status = $status, c.evidence_ids = $evidence_ids, c.wording = $wording
            CREATE (r)-[:{REL_PRODUCED_ANSWER}]->(c)
            """,
            {"replay_id": fields["id"], **claim},
        )
        for evidence_id in claim["evidence_id_list"]:
            run(
                graph,
                f"""
                MATCH (c:{LABEL_ANSWER_CLAIM} {{id: $claim_id}})
                MATCH (a:{LABEL_ASSERTION} {{id: $assertion_id}})
                CREATE (c)-[:{REL_SUPPORTED_BY_ASSERTION}]->(a)
                """,
                {"claim_id": claim["claim_id"], "assertion_id": evidence_id},
            )


def load_replay(graph: Any, replay_id: str) -> dict[str, Any] | None:
    found = records(
        run(
            graph,
            f"""
            MATCH (r:{LABEL_REPLAY_RUN} {{id: $replay_id}})
            OPTIONAL MATCH (r)-[:{REL_PRODUCED_ANSWER}]->(c:{LABEL_ANSWER_CLAIM})
            RETURN r.id AS replay_id, r.snapshot_id AS snapshot_id, r.question AS question,
                   r.predicate AS predicate, r.policy_version AS policy_version,
                   r.prompt_version AS prompt_version, r.model_version AS model_version,
                   r.citation_rejected AS citation_rejected, r.idempotency_key AS idempotency_key,
                   c.id AS claim_id, c.predicate AS claim_predicate, c.value AS value,
                   c.status AS status, c.evidence_ids AS evidence_ids, c.wording AS wording
            """,
            {"replay_id": replay_id},
        )
    )
    if not found or not found[0].get("replay_id"):
        return None
    return {"rows": found}


def find_task_id_by_idempotency(graph: Any, idempotency_key: str) -> str | None:
    found = records(
        run(
            graph,
            f"""
            MATCH (t:{LABEL_TASK} {{idempotency_key: $idempotency_key}})
            RETURN t.id AS task_id
            """,
            {"idempotency_key": idempotency_key},
        )
    )
    if not found or not found[0].get("task_id"):
        return None
    return str(found[0]["task_id"])


def find_handoff_task_id(graph: Any, idempotency_key: str) -> str | None:
    found = records(
        run(
            graph,
            f"""
            MATCH (t:{LABEL_TASK})-[:{REL_HAS_HANDOFF}]->
                  (h:{LABEL_HANDOFF} {{idempotency_key: $idempotency_key}})
            RETURN t.id AS task_id
            """,
            {"idempotency_key": idempotency_key},
        )
    )
    if not found or not found[0].get("task_id"):
        return None
    return str(found[0]["task_id"])


def insert_task(graph: Any, fields: dict[str, Any]) -> None:
    run(
        graph,
        f"""
        MATCH (ag:{LABEL_AGENT} {{id: $owner_agent_id}})
        CREATE (t:{LABEL_TASK})
        SET t.id = $id, t.objective = $objective, t.status = $status,
            t.version = $version, t.acceptance_criteria = $acceptance_criteria,
            t.idempotency_key = $idempotency_key, t.created_at = $created_at
        CREATE (ag)-[:{REL_OWNS_TASK}]->(t)
        """,
        fields,
    )


def insert_handoff(graph: Any, fields: dict[str, Any]) -> None:
    run(
        graph,
        f"""
        MATCH (t:{LABEL_TASK} {{id: $task_id}})
        MATCH (recipient:{LABEL_AGENT} {{id: $to_agent_id}})
        MATCH (snap:{LABEL_SNAPSHOT} {{id: $snapshot_id}})
        CREATE (h:{LABEL_HANDOFF})
        SET h.id = $id, h.from_agent_id = $from_agent_id, h.to_agent_id = $to_agent_id,
            h.open_questions = $open_questions, h.expires_at = $expires_at,
            h.idempotency_key = $idempotency_key, h.created_at = $created_at,
            h.result = '', h.evidence_refs = '[]'
        CREATE (t)-[:{REL_HAS_HANDOFF}]->(h)
        CREATE (h)-[:{REL_ASSIGNED_TO}]->(recipient)
        CREATE (h)-[:{REL_USED_SNAPSHOT}]->(snap)
        SET t.status = $status, t.version = $version
        """,
        fields,
    )
    for ref in fields["memory_refs"]:
        _link_memory_ref(graph, fields["id"], ref)
    for assertion_id in fields["conflict_ids"]:
        run(
            graph,
            f"""
            MATCH (h:{LABEL_HANDOFF} {{id: $handoff_id}})
            MATCH (a:{LABEL_ASSERTION} {{id: $assertion_id}})
            CREATE (h)-[:{REL_INCLUDES_CONFLICT}]->(a)
            """,
            {"handoff_id": fields["id"], "assertion_id": assertion_id},
        )


def _link_memory_ref(graph: Any, handoff_id: str, ref: dict[str, str]) -> None:
    label = LABEL_ASSERTION if ref["kind"] == "assertion" else LABEL_SOURCE
    run(
        graph,
        f"""
        MATCH (h:{LABEL_HANDOFF} {{id: $handoff_id}})
        MATCH (n:{label} {{id: $ref_id}})
        CREATE (h)-[:{REL_REFERENCES_MEMORY}]->(n)
        """,
        {"handoff_id": handoff_id, "ref_id": ref["id"]},
    )


def set_task_owner(graph: Any, task_id: str, owner_id: str, status: str, version: int) -> None:
    run(
        graph,
        f"""
        MATCH (t:{LABEL_TASK} {{id: $task_id}})
        OPTIONAL MATCH (:{LABEL_AGENT})-[owns:{REL_OWNS_TASK}]->(t)
        DELETE owns
        """,
        {"task_id": task_id},
    )
    run(
        graph,
        f"""
        MATCH (t:{LABEL_TASK} {{id: $task_id}})
        MATCH (ag:{LABEL_AGENT} {{id: $owner_id}})
        CREATE (ag)-[:{REL_OWNS_TASK}]->(t)
        SET t.status = $status, t.version = $version
        """,
        {
            "task_id": task_id,
            "owner_id": owner_id,
            "status": status,
            "version": version,
        },
    )


def complete_task(
    graph: Any,
    task_id: str,
    *,
    status: str,
    version: int,
    result: str,
    evidence_refs: str,
) -> None:
    run(
        graph,
        f"""
        MATCH (t:{LABEL_TASK} {{id: $task_id}})-[:{REL_HAS_HANDOFF}]->(h:{LABEL_HANDOFF})
        SET t.status = $status, t.version = $version,
            h.result = $result, h.evidence_refs = $evidence_refs
        """,
        {
            "task_id": task_id,
            "status": status,
            "version": version,
            "result": result,
            "evidence_refs": evidence_refs,
        },
    )


def replace_handoff_snapshot(
    graph: Any,
    *,
    task_id: str,
    handoff_id: str,
    snapshot_id: str,
    conflict_ids: list[str],
    version: int,
    expires_at: str | None,
) -> None:
    run(
        graph,
        f"""
        MATCH (h:{LABEL_HANDOFF} {{id: $handoff_id}})-[old:{REL_USED_SNAPSHOT}]->(:{LABEL_SNAPSHOT})
        DELETE old
        """,
        {"handoff_id": handoff_id},
    )
    run(
        graph,
        f"""
        MATCH (h:{LABEL_HANDOFF} {{id: $handoff_id}})
        MATCH (s:{LABEL_SNAPSHOT} {{id: $snapshot_id}})
        CREATE (h)-[:{REL_USED_SNAPSHOT}]->(s)
        """,
        {"handoff_id": handoff_id, "snapshot_id": snapshot_id},
    )
    run(
        graph,
        f"""
        MATCH (h:{LABEL_HANDOFF} {{id: $handoff_id}})-[edge:{REL_INCLUDES_CONFLICT}]->()
        DELETE edge
        """,
        {"handoff_id": handoff_id},
    )
    for assertion_id in conflict_ids:
        run(
            graph,
            f"""
            MATCH (h:{LABEL_HANDOFF} {{id: $handoff_id}})
            MATCH (a:{LABEL_ASSERTION} {{id: $assertion_id}})
            CREATE (h)-[:{REL_INCLUDES_CONFLICT}]->(a)
            """,
            {"handoff_id": handoff_id, "assertion_id": assertion_id},
        )
    params: dict[str, Any] = {"task_id": task_id, "version": version}
    assignment = "t.version = $version"
    if expires_at is not None:
        assignment = "t.version = $version, h.expires_at = $expires_at"
        params["expires_at"] = expires_at
        params["handoff_id"] = handoff_id
        run(
            graph,
            f"""
            MATCH (t:{LABEL_TASK} {{id: $task_id}})-[:{REL_HAS_HANDOFF}]->
                  (h:{LABEL_HANDOFF} {{id: $handoff_id}})
            SET {assignment}
            """,
            params,
        )
        return
    run(
        graph,
        f"""
        MATCH (t:{LABEL_TASK} {{id: $task_id}})
        SET {assignment}
        """,
        params,
    )


def load_task(graph: Any, task_id: str) -> dict[str, Any] | None:
    found = records(
        run(
            graph,
            f"""
            MATCH (owner:{LABEL_AGENT})-[:{REL_OWNS_TASK}]->(t:{LABEL_TASK} {{id: $task_id}})
            OPTIONAL MATCH (t)-[:{REL_HAS_HANDOFF}]->(h:{LABEL_HANDOFF})
            OPTIONAL MATCH (h)-[:{REL_USED_SNAPSHOT}]->(s:{LABEL_SNAPSHOT})
            RETURN t.id AS task_id, t.objective AS objective, t.status AS status,
                   t.version AS version, t.acceptance_criteria AS acceptance_criteria,
                   t.idempotency_key AS idempotency_key, owner.id AS owner_agent_id,
                   h.id AS handoff_id, h.from_agent_id AS from_agent_id,
                   h.to_agent_id AS to_agent_id, h.open_questions AS open_questions,
                   h.expires_at AS expires_at, h.result AS result,
                   h.evidence_refs AS evidence_refs, s.id AS snapshot_id,
                   s.as_of_time AS as_of_time
            """,
            {"task_id": task_id},
        )
    )
    if not found or not found[0].get("task_id"):
        return None
    row = found[0]
    if row.get("handoff_id"):
        row["memory_refs"] = _handoff_refs(graph, str(row["handoff_id"]))
        row["conflicts"] = _handoff_conflicts(graph, str(row["handoff_id"]))
        row["entity_ids"] = _snapshot_entities(graph, str(row.get("snapshot_id") or ""))
    else:
        row["memory_refs"] = []
        row["conflicts"] = []
        row["entity_ids"] = []
    return row


def newer_memory(graph: Any, as_of: str) -> list[dict[str, Any]]:
    return records(
        run(
            graph,
            f"""
            MATCH (a:{LABEL_ASSERTION})-[:{REL_ABOUT}]->(e:{LABEL_ENTITY})
            WHERE a.observed_at > $as_of AND (a.status = 'current' OR a.status = 'disputed')
            RETURN a.id AS assertion_id, a.predicate AS predicate, e.id AS entity_id
            """,
            {"as_of": as_of},
        )
    )


def _handoff_refs(graph: Any, handoff_id: str) -> list[str]:
    found = records(
        run(
            graph,
            f"""
            MATCH (h:{LABEL_HANDOFF} {{id: $handoff_id}})-[:{REL_REFERENCES_MEMORY}]->(n)
            RETURN n.id AS ref_id
            """,
            {"handoff_id": handoff_id},
        )
    )
    return [str(row["ref_id"]) for row in found if row.get("ref_id")]


def _handoff_conflicts(graph: Any, handoff_id: str) -> list[dict[str, Any]]:
    return records(
        run(
            graph,
            f"""
            MATCH (h:{LABEL_HANDOFF} {{id: $handoff_id}})-[:{REL_INCLUDES_CONFLICT}]->
                  (a:{LABEL_ASSERTION})
            OPTIONAL MATCH (a)-[:{REL_SUPPORTED_BY}]->(s:{LABEL_SOURCE})
            RETURN a.id AS assertion_id, a.predicate AS predicate, a.value AS value,
                   s.id AS source_id
            """,
            {"handoff_id": handoff_id},
        )
    )


_BENCH_EDGES = {
    REL_SUPPORTED_BY: LABEL_SOURCE,
    REL_SUPERSEDES: LABEL_ASSERTION,
}


def relationship_exists(graph: Any, rel: str, from_id: str, to_id: str) -> bool:
    target = _BENCH_EDGES[rel]
    found = records(
        run(
            graph,
            f"""
            MATCH (a:{LABEL_ASSERTION} {{id: $from_id}})-[r:{rel}]->(b:{target} {{id: $to_id}})
            RETURN count(r) AS total
            """,
            {"from_id": from_id, "to_id": to_id},
        )
    )
    if not found:
        return False
    return int(found[0].get("total") or 0) > 0


def delete_relationship(graph: Any, rel: str, from_id: str, to_id: str) -> None:
    target = _BENCH_EDGES[rel]
    run(
        graph,
        f"""
        MATCH (a:{LABEL_ASSERTION} {{id: $from_id}})-[r:{rel}]->(b:{target} {{id: $to_id}})
        DELETE r
        """,
        {"from_id": from_id, "to_id": to_id},
    )


def create_relationship(graph: Any, rel: str, from_id: str, to_id: str) -> None:
    target = _BENCH_EDGES[rel]
    run(
        graph,
        f"""
        MATCH (a:{LABEL_ASSERTION} {{id: $from_id}}), (b:{target} {{id: $to_id}})
        MERGE (a)-[:{rel}]->(b)
        """,
        {"from_id": from_id, "to_id": to_id},
    )


def graph_size(graph: Any) -> dict[str, int]:
    return {
        "nodes": _count(graph, "MATCH (n) RETURN count(n) AS total"),
        "edges": _count(graph, "MATCH ()-[r]->() RETURN count(r) AS total"),
        "assertions": _count(
            graph,
            f"MATCH (a:{LABEL_ASSERTION}) RETURN count(a) AS total",
        ),
    }


def _count(graph: Any, statement: str) -> int:
    found = records(run(graph, statement))
    if not found:
        return 0
    return int(found[0].get("total") or 0)


def _snapshot_entities(graph: Any, snapshot_id: str) -> list[str]:
    if not snapshot_id:
        return []
    found = records(
        run(
            graph,
            f"""
            MATCH (s:{LABEL_SNAPSHOT} {{id: $snapshot_id}})-[:{REL_ABOUT}]->(e:{LABEL_ENTITY})
            RETURN e.id AS entity_id
            """,
            {"snapshot_id": snapshot_id},
        )
    )
    return [str(row["entity_id"]) for row in found if row.get("entity_id")]

