"""Delete one graph edge, measure the answer, and put the edge back."""

from __future__ import annotations

from datetime import UTC, datetime

from faultline.config import Settings
from faultline.constants import REL_SUPERSEDES, REL_SUPPORTED_BY
from faultline.errors import FaultlineError
from faultline.graph import repository as repo
from faultline.graph.client import GraphStore
from faultline.memory.ids import new_id
from faultline.replay.answer import DeterministicAnswerer
from faultline.replay.service import LabService
from faultline.schemas.models import AblationReport, BenchClaim, IncludedFact

LATE = datetime(2026, 10, 16, 13, 0, tzinfo=UTC)
QUESTION = "Which deployment region should the rollout use?"
ENTITY_ID = "project-atlas"
REGION_B = "assert-region-b"
REGION_A = "assert-region-a"
SOURCE_B = "source-change-002"
TENANT_ID = "tenant-synthetic"


def run_ablation(settings: Settings, store: GraphStore, tenant_id: str) -> AblationReport:
    if settings.app_env != "development":
        raise FaultlineError("validation_error", "Benchmarks run only in development", 400)
    if tenant_id != TENANT_ID:
        raise FaultlineError("not_found", "Benchmark not found", 404)
    graph = store.graph_for_tenant(tenant_id)
    if repo.find_assertion_brief(graph, REGION_B) is None:
        raise FaultlineError("not_found", "Assertion not found", 404)
    lab = LabService(settings, store, DeterministicAnswerer())
    intact = _claim(lab, tenant_id, "intact")
    support_deleted = _without_edge(
        lab,
        graph,
        tenant_id,
        REL_SUPPORTED_BY,
        REGION_B,
        SOURCE_B,
        "support",
    )
    supersedes_deleted = _without_edge(
        lab,
        graph,
        tenant_id,
        REL_SUPERSEDES,
        REGION_B,
        REGION_A,
        "supersedes",
    )
    restored = repo.relationship_exists(
        graph, REL_SUPPORTED_BY, REGION_B, SOURCE_B
    ) and repo.relationship_exists(graph, REL_SUPERSEDES, REGION_B, REGION_A)
    return AblationReport(
        intact=intact,
        support_deleted=support_deleted,
        supersedes_deleted=supersedes_deleted,
        restored=restored,
    )


def _without_edge(lab, graph, tenant_id, rel, from_id, to_id, name) -> BenchClaim:
    repo.delete_relationship(graph, rel, from_id, to_id)
    try:
        return _claim(lab, tenant_id, name)
    finally:
        repo.create_relationship(graph, rel, from_id, to_id)


def _claim(lab: LabService, tenant_id: str, name: str) -> BenchClaim:
    stamp = new_id("bench")
    snapshot, _created = lab.create_snapshot(
        tenant_id,
        as_of_time=LATE,
        time_mode="known",
        entity_ids=[ENTITY_ID],
        predicate="deploy_region",
        exclude_source_ids=[],
        idempotency_key=f"bench-snap:{name}:{stamp}",
    )
    replay, _replay_created = lab.create_replay(
        tenant_id,
        question=QUESTION,
        predicate="deploy_region",
        snapshot_id=snapshot.snapshot_id,
        idempotency_key=f"bench-replay:{name}:{stamp}",
    )
    claim = replay.claims[0]
    return BenchClaim(
        status=claim.status,
        value=claim.value,
        evidence_ids=list(claim.evidence_ids),
        included=[
            IncludedFact(
                assertion_id=member.assertion_id,
                status=member.status,
                value=member.value,
            )
            for member in snapshot.included
        ],
    )
