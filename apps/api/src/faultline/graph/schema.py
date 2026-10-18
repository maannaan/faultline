"""Indexes and the schema version node for one tenant graph."""

from __future__ import annotations

import logging
from typing import Any

from faultline.constants import (
    LABEL_AGENT,
    LABEL_ANSWER_CLAIM,
    LABEL_ASSERTION,
    LABEL_ENTITY,
    LABEL_HANDOFF,
    LABEL_MEMORY_EVENT,
    LABEL_REPLAY_RUN,
    LABEL_SCHEMA_META,
    LABEL_SESSION,
    LABEL_SNAPSHOT,
    LABEL_SOURCE,
    LABEL_TASK,
    LABEL_TENANT,
    LABEL_USER,
    REL_HAS_AGENT,
    REL_HAS_USER,
    REL_STARTED_SESSION,
    SCHEMA_NODE_ID,
    SYSTEM_AGENT_ID,
    SYSTEM_AGENT_ROLE,
    SYSTEM_AGENT_VERSION,
    SYSTEM_SESSION_ID,
    SYSTEM_USER_ID,
)
from faultline.errors import FaultlineError
from faultline.graph.cypher import records, run

logger = logging.getLogger("faultline.schema")

_INDEXES = (
    (LABEL_ASSERTION, "id"),
    (LABEL_ASSERTION, "idempotency_key"),
    (LABEL_ENTITY, "id"),
    (LABEL_ENTITY, "normalized_name"),
    (LABEL_ENTITY, "normalized_type"),
    (LABEL_SOURCE, "id"),
    (LABEL_MEMORY_EVENT, "id"),
    (LABEL_MEMORY_EVENT, "idempotency_key"),
    (LABEL_SESSION, "id"),
    (LABEL_AGENT, "id"),
    (LABEL_USER, "id"),
    (LABEL_SNAPSHOT, "id"),
    (LABEL_SNAPSHOT, "idempotency_key"),
    (LABEL_REPLAY_RUN, "id"),
    (LABEL_REPLAY_RUN, "idempotency_key"),
    (LABEL_ANSWER_CLAIM, "id"),
    (LABEL_TASK, "id"),
    (LABEL_TASK, "idempotency_key"),
    (LABEL_HANDOFF, "id"),
    (LABEL_HANDOFF, "idempotency_key"),
)


def _already_indexed(exc: Exception) -> bool:
    message = str(exc).lower()
    return "already indexed" in message or "index already exists" in message


def ensure_schema(graph: Any, tenant_id: str, schema_version: str) -> None:
    for label, prop in _INDEXES:
        if not label.isidentifier() or not prop.isidentifier():
            raise RuntimeError("Refusing to build an index from an unsafe name")
        statement = f"CREATE INDEX FOR (n:{label}) ON (n.{prop})"
        try:
            run(graph, statement)
        except Exception as exc:
            if _already_indexed(exc):
                continue
            logger.warning(
                "index creation failed for %s.%s: %s",
                label,
                prop,
                exc.__class__.__name__,
            )
            raise

    found = records(
        run(
            graph,
            f"MATCH (s:{LABEL_SCHEMA_META} {{id: $id}}) RETURN s.version AS version",
            {"id": SCHEMA_NODE_ID},
        )
    )
    if found and str(found[0].get("version")) != schema_version:
        raise FaultlineError(
            "schema_mismatch",
            f"Graph schema is {found[0].get('version')}, application expects {schema_version}",
            500,
        )
    run(
        graph,
        f"""
        MERGE (s:{LABEL_SCHEMA_META} {{id: $id}})
        SET s.version = $version
        """,
        {"id": SCHEMA_NODE_ID, "version": schema_version},
    )
    run(
        graph,
        f"""
        MERGE (t:{LABEL_TENANT} {{id: $tenant_id}})
        SET t.name = $tenant_id
        """,
        {"tenant_id": tenant_id},
    )
    run(
        graph,
        f"""
        MATCH (t:{LABEL_TENANT} {{id: $tenant_id}})
        MERGE (u:{LABEL_USER} {{id: $user_id}})
        SET u.tenant_id = $tenant_id
        MERGE (t)-[:{REL_HAS_USER}]->(u)
        MERGE (ag:{LABEL_AGENT} {{id: $agent_id}})
        ON CREATE SET ag.role = $role, ag.version = $agent_version, ag.tenant_id = $tenant_id
        MERGE (t)-[:{REL_HAS_AGENT}]->(ag)
        MERGE (se:{LABEL_SESSION} {{id: $session_id}})
        ON CREATE SET se.started_at = $started_at
        MERGE (u)-[:{REL_STARTED_SESSION}]->(se)
        """,
        {
            "tenant_id": tenant_id,
            "user_id": SYSTEM_USER_ID,
            "agent_id": SYSTEM_AGENT_ID,
            "role": SYSTEM_AGENT_ROLE,
            "agent_version": SYSTEM_AGENT_VERSION,
            "session_id": SYSTEM_SESSION_ID,
            "started_at": "1970-01-01T00:00:00Z",
        },
    )
