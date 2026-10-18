"""Correction blast radius: what relied on an assertion, and is it outdated now?

Reverse traversals from one assertion to the snapshots that included it, the
replays whose answers cited it, and the handoffs built on those snapshots. The
status each one saw is the `status_at_snapshot` stored on INCLUDES_ASSERTION.
Something is outdated when that status differs from the assertion's status now.
Nothing is written.
"""

from __future__ import annotations

from typing import Any

from faultline.constants import (
    LABEL_ANSWER_CLAIM,
    LABEL_ASSERTION,
    LABEL_HANDOFF,
    LABEL_REPLAY_RUN,
    LABEL_SNAPSHOT,
    LABEL_SOURCE,
    LABEL_TASK,
    REL_CONFLICTS_WITH,
    REL_HAS_HANDOFF,
    REL_INCLUDES_ASSERTION,
    REL_INCLUDES_CONFLICT,
    REL_PRODUCED_ANSWER,
    REL_REFERENCES_MEMORY,
    REL_SUPERSEDES,
    REL_SUPPORTED_BY,
    REL_SUPPORTED_BY_ASSERTION,
    REL_USED_SNAPSHOT,
)
from faultline.errors import FaultlineError
from faultline.graph.cypher import as_list, records, run
from faultline.schemas.models import (
    ImpactAssertion,
    ImpactHandoff,
    ImpactReplay,
    ImpactReport,
    ImpactSnapshot,
)

_LIMIT = 100


def assertion_impact(graph: Any, assertion_id: str) -> ImpactReport:
    params = {"id": assertion_id, "limit": _LIMIT}
    head = records(
        run(
            graph,
            f"""
            MATCH (a:{LABEL_ASSERTION} {{id: $id}})
            RETURN a.id AS assertion_id, a.predicate AS predicate, a.value AS value,
                   a.status AS status_now,
                   [(newer)-[:{REL_SUPERSEDES}]->(a) | newer.id] AS superseded_by,
                   [(a)-[:{REL_CONFLICTS_WITH}]-(other) | other.id] AS conflicts_with
            """,
            params,
        )
    )
    if not head:
        raise FaultlineError("not_found", "Assertion not found", 404)
    row = head[0]
    now = str(row["status_now"])

    snapshots = [
        ImpactSnapshot(
            snapshot_id=str(item["snapshot_id"]),
            as_of=str(item["as_of"]),
            status_then=str(item["status_then"]),
            outdated=str(item["status_then"]) != now,
            replay_count=int(item["replay_count"] or 0),
            handoff_count=int(item["handoff_count"] or 0),
        )
        for item in records(
            run(
                graph,
                f"""
                MATCH (s:{LABEL_SNAPSHOT})-[inc:{REL_INCLUDES_ASSERTION}]
                      ->(:{LABEL_ASSERTION} {{id: $id}})
                RETURN s.id AS snapshot_id, s.as_of_time AS as_of,
                       inc.status_at_snapshot AS status_then,
                       size([(r:{LABEL_REPLAY_RUN})-[:{REL_USED_SNAPSHOT}]->(s) | r])
                           AS replay_count,
                       size([(h:{LABEL_HANDOFF})-[:{REL_USED_SNAPSHOT}]->(s) | h])
                           AS handoff_count
                ORDER BY as_of, snapshot_id
                LIMIT $limit
                """,
                params,
            )
        )
    ]

    replays = [
        ImpactReplay(
            replay_id=str(item["replay_id"]),
            question=str(item["question"] or ""),
            snapshot_id=str(item["snapshot_id"]),
            as_of=str(item["as_of"]),
            claim_status=str(item["claim_status"]),
            claim_value=(str(item["claim_value"]) if item.get("claim_value") else None),
            status_then=str(item["status_then"]),
            outdated=str(item["status_then"]) != now,
        )
        for item in records(
            run(
                graph,
                f"""
                MATCH (r:{LABEL_REPLAY_RUN})-[:{REL_PRODUCED_ANSWER}]->(c:{LABEL_ANSWER_CLAIM})
                      -[:{REL_SUPPORTED_BY_ASSERTION}]->(a:{LABEL_ASSERTION} {{id: $id}})
                MATCH (r)-[:{REL_USED_SNAPSHOT}]->(s:{LABEL_SNAPSHOT})
                      -[inc:{REL_INCLUDES_ASSERTION}]->(a)
                RETURN r.id AS replay_id, r.question AS question, s.id AS snapshot_id,
                       s.as_of_time AS as_of, c.status AS claim_status, c.value AS claim_value,
                       inc.status_at_snapshot AS status_then
                ORDER BY as_of, replay_id
                LIMIT $limit
                """,
                params,
            )
        )
    ]

    handoffs = [
        ImpactHandoff(
            handoff_id=str(item["handoff_id"]),
            task_id=str(item["task_id"]),
            objective=str(item["objective"] or ""),
            task_status=str(item["task_status"] or ""),
            snapshot_id=str(item["snapshot_id"]),
            as_of=str(item["as_of"]),
            status_then=str(item["status_then"]),
            referenced=int(item["direct_refs"] or 0) + int(item["source_refs"] or 0) > 0,
            carried_as_conflict=int(item["conflict_refs"] or 0) > 0,
            outdated=str(item["status_then"]) != now,
        )
        for item in records(
            run(
                graph,
                f"""
                MATCH (t:{LABEL_TASK})-[:{REL_HAS_HANDOFF}]->(h:{LABEL_HANDOFF})
                      -[:{REL_USED_SNAPSHOT}]->(s:{LABEL_SNAPSHOT})
                      -[inc:{REL_INCLUDES_ASSERTION}]->(a:{LABEL_ASSERTION} {{id: $id}})
                RETURN h.id AS handoff_id, t.id AS task_id, t.objective AS objective,
                       t.status AS task_status, s.id AS snapshot_id, s.as_of_time AS as_of,
                       inc.status_at_snapshot AS status_then,
                       size([(h)-[:{REL_REFERENCES_MEMORY}]->(a) | a]) AS direct_refs,
                       size([(h)-[:{REL_REFERENCES_MEMORY}]->(:{LABEL_SOURCE})
                             <-[:{REL_SUPPORTED_BY}]-(a) | a]) AS source_refs,
                       size([(h)-[:{REL_INCLUDES_CONFLICT}]->(a) | a]) AS conflict_refs
                ORDER BY as_of, handoff_id
                LIMIT $limit
                """,
                params,
            )
        )
    ]

    outdated = sum(item.outdated for item in [*snapshots, *replays, *handoffs])
    return ImpactReport(
        assertion=ImpactAssertion(
            assertion_id=str(row["assertion_id"]),
            predicate=str(row["predicate"]),
            value=str(row["value"]),
            status_now=now,
            superseded_by=as_list(row.get("superseded_by")),
            conflicts_with=as_list(row.get("conflicts_with")),
        ),
        snapshots=snapshots,
        replays=replays,
        handoffs=handoffs,
        outdated_count=outdated,
        summary=_summary(str(row["assertion_id"]), now, snapshots, replays, handoffs),
    )


def _summary(
    assertion_id: str,
    now: str,
    snapshots: list[ImpactSnapshot],
    replays: list[ImpactReplay],
    handoffs: list[ImpactHandoff],
) -> str:
    if not (snapshots or replays or handoffs):
        return f"Nothing recorded relied on {assertion_id} yet."
    stale_replays = sum(item.outdated for item in replays)
    stale_handoffs = sum(item.outdated for item in handoffs)
    stale_snapshots = sum(item.outdated for item in snapshots)
    if not (stale_replays or stale_handoffs or stale_snapshots):
        return f"{assertion_id} is {now}, and everything that used it saw the same status."
    return (
        f"{assertion_id} is now {now}. {stale_snapshots} snapshot(s), {stale_replays} replay "
        f"answer(s) and {stale_handoffs} handoff(s) saw a different status and need review."
    )
