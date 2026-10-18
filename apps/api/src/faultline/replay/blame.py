"""Blame an answer: follow each claim's edges back to the agent that recorded it.

AnswerClaim -SUPPORTED_BY_ASSERTION-> Assertion -SUPPORTED_BY-> Source, and
MemoryEvent -CREATED_ASSERTION-> Assertion, Session -CONTAINS_EVENT-> MemoryEvent,
Agent -RECORDED-> MemoryEvent. The status the replay saw comes from the snapshot's
INCLUDES_ASSERTION edge. Nothing is written.
"""

from __future__ import annotations

from typing import Any

from faultline.constants import (
    LABEL_AGENT,
    LABEL_ANSWER_CLAIM,
    LABEL_ASSERTION,
    LABEL_MEMORY_EVENT,
    LABEL_REPLAY_RUN,
    LABEL_SESSION,
    LABEL_SNAPSHOT,
    LABEL_SOURCE,
    REL_CONTAINS_EVENT,
    REL_INCLUDES_ASSERTION,
    REL_PRODUCED_ANSWER,
    REL_RECORDED,
    REL_SUPPORTED_BY,
    REL_SUPPORTED_BY_ASSERTION,
    REL_USED_SNAPSHOT,
)
from faultline.errors import FaultlineError
from faultline.graph.cypher import records, run
from faultline.schemas.models import BlameClaim, BlameHop, BlameReport, ReplayList, ReplaySummary


def list_replays(graph: Any, limit: int) -> ReplayList:
    rows = records(
        run(
            graph,
            f"""
            MATCH (r:{LABEL_REPLAY_RUN})-[:{REL_USED_SNAPSHOT}]->(s:{LABEL_SNAPSHOT})
            OPTIONAL MATCH (r)-[:{REL_PRODUCED_ANSWER}]->(c:{LABEL_ANSWER_CLAIM})
            WITH r, s, collect(c)[0] AS c
            RETURN r.id AS replay_id, r.question AS question, r.predicate AS predicate,
                   s.id AS snapshot_id, s.as_of_time AS as_of, r.created_at AS created_at,
                   c.status AS claim_status, c.value AS claim_value
            ORDER BY created_at DESC
            LIMIT $limit
            """,
            {"limit": limit},
        )
    )
    return ReplayList(
        replays=[
            ReplaySummary(
                replay_id=str(row["replay_id"]),
                question=str(row.get("question") or ""),
                predicate=str(row.get("predicate") or ""),
                snapshot_id=str(row["snapshot_id"]),
                as_of=str(row.get("as_of") or ""),
                created_at=str(row.get("created_at") or ""),
                claim_status=str(row.get("claim_status") or "insufficient"),
                claim_value=_opt(row.get("claim_value")),
            )
            for row in rows
        ]
    )


def blame_replay(graph: Any, replay_id: str) -> BlameReport:
    head = records(
        run(
            graph,
            f"""
            MATCH (r:{LABEL_REPLAY_RUN} {{id: $id}})-[:{REL_USED_SNAPSHOT}]->(s:{LABEL_SNAPSHOT})
            RETURN r.id AS replay_id, r.question AS question, r.predicate AS predicate,
                   r.model_version AS model_version, r.prompt_version AS prompt_version,
                   s.id AS snapshot_id, s.as_of_time AS as_of
            """,
            {"id": replay_id},
        )
    )
    if not head:
        raise FaultlineError("not_found", "Replay not found", 404)
    rows = records(
        run(
            graph,
            f"""
            MATCH (r:{LABEL_REPLAY_RUN} {{id: $id}})
                  -[:{REL_PRODUCED_ANSWER}]->(c:{LABEL_ANSWER_CLAIM})
            MATCH (r)-[:{REL_USED_SNAPSHOT}]->(s:{LABEL_SNAPSHOT})
            OPTIONAL MATCH (c)-[:{REL_SUPPORTED_BY_ASSERTION}]->(a:{LABEL_ASSERTION})
            OPTIONAL MATCH (s)-[inc:{REL_INCLUDES_ASSERTION}]->(a)
            OPTIONAL MATCH (a)-[:{REL_SUPPORTED_BY}]->(src:{LABEL_SOURCE})
            OPTIONAL MATCH (ev:{LABEL_MEMORY_EVENT} {{id: a.origin_event_id}})
            OPTIONAL MATCH (se:{LABEL_SESSION})-[:{REL_CONTAINS_EVENT}]->(ev)
            OPTIONAL MATCH (ag:{LABEL_AGENT})-[:{REL_RECORDED}]->(ev)
            RETURN c.id AS claim_id, c.status AS claim_status, c.value AS claim_value,
                   c.wording AS wording,
                   a.id AS assertion_id, a.predicate AS predicate, a.value AS value,
                   inc.status_at_snapshot AS status_then, a.status AS status_now,
                   a.observed_at AS observed_at,
                   src.id AS source_id, src.title AS source_title,
                   src.trust_tier AS trust_tier, src.excerpt AS excerpt,
                   ev.id AS event_id, se.id AS session_id, ag.id AS agent_id
            ORDER BY claim_id, observed_at
            """,
            {"id": replay_id},
        )
    )
    claims: dict[str, BlameClaim] = {}
    for row in rows:
        claim_id = str(row["claim_id"])
        claim = claims.get(claim_id)
        if claim is None:
            claim = BlameClaim(
                claim_id=claim_id,
                status=str(row.get("claim_status") or ""),
                value=_opt(row.get("claim_value")),
                wording=str(row.get("wording") or ""),
                chain=[],
            )
            claims[claim_id] = claim
        if row.get("assertion_id") and not any(
            hop.assertion_id == row["assertion_id"] for hop in claim.chain
        ):
            claim.chain.append(
                BlameHop(
                    assertion_id=str(row["assertion_id"]),
                    predicate=str(row.get("predicate") or ""),
                    value=str(row.get("value") or ""),
                    status_then=_opt(row.get("status_then")),
                    status_now=str(row.get("status_now") or ""),
                    observed_at=str(row.get("observed_at") or ""),
                    source_id=_opt(row.get("source_id")),
                    source_title=_opt(row.get("source_title")),
                    trust_tier=_opt(row.get("trust_tier")),
                    excerpt=_opt(row.get("excerpt")),
                    event_id=_opt(row.get("event_id")),
                    session_id=_opt(row.get("session_id")),
                    agent_id=_opt(row.get("agent_id")),
                )
            )
    meta = head[0]
    return BlameReport(
        replay_id=str(meta["replay_id"]),
        question=str(meta.get("question") or ""),
        predicate=str(meta.get("predicate") or ""),
        model_version=str(meta.get("model_version") or ""),
        prompt_version=str(meta.get("prompt_version") or ""),
        snapshot_id=str(meta["snapshot_id"]),
        as_of=str(meta.get("as_of") or ""),
        claims=list(claims.values()),
    )


def _opt(value: object) -> str | None:
    if value is None or value == "":
        return None
    return str(value)
