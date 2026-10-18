"""Seed Project Atlas through the same write path the API uses."""

from __future__ import annotations

from datetime import UTC, datetime

from faultline.config import get_settings
from faultline.constants import KNOWN_TENANTS
from faultline.graph.client import GraphStore
from faultline.memory.service import MemoryService

TENANT_ID = KNOWN_TENANTS[0]
ENTITY_ID = "project-atlas"


def seed_atlas(settings=None, store: GraphStore | None = None) -> None:
    settings = settings or get_settings()
    store = store or GraphStore(settings)
    service = MemoryService(settings, store)
    service.ensure_user(TENANT_ID, "user-dev")
    service.ensure_agent(TENANT_ID, "agent-planner", "planner", "0.1")
    service.ensure_agent(TENANT_ID, "agent-release", "release", "0.1")
    service.ensure_session(
        TENANT_ID,
        "session-atlas-seed",
        "user-dev",
        datetime(2026, 10, 15, 8, 0, tzinfo=UTC),
    )
    service.ensure_entity(
        TENANT_ID,
        entity_id=ENTITY_ID,
        canonical_name="Project Atlas",
        entity_type="Project",
    )
    _source(
        service,
        source_id="source-design-001",
        title="Atlas design note",
        text="Project Atlas deployment region is region-a.",
        observed_at=datetime(2026, 10, 15, 9, 0, tzinfo=UTC),
        event_id="evt-source-design-001",
    )
    _assertion(
        service,
        assertion_id="assert-region-a",
        predicate="deploy_region",
        value="region-a",
        source_id="source-design-001",
        observed_at=datetime(2026, 10, 15, 9, 0, tzinfo=UTC),
        valid_from=datetime(2026, 10, 15, 9, 0, tzinfo=UTC),
        confidence=0.99,
        idempotency_key="seed:assert-region-a",
        event_id="evt-assert-region-a",
    )
    _source(
        service,
        source_id="source-change-002",
        title="Atlas change record",
        text="Project Atlas deployment region is region-b. This corrects assert-region-a.",
        observed_at=datetime(2026, 10, 16, 10, 0, tzinfo=UTC),
        event_id="evt-source-change-002",
    )
    _assertion(
        service,
        assertion_id="assert-region-b",
        predicate="deploy_region",
        value="region-b",
        source_id="source-change-002",
        observed_at=datetime(2026, 10, 16, 10, 0, tzinfo=UTC),
        valid_from=datetime(2026, 10, 16, 10, 0, tzinfo=UTC),
        confidence=0.99,
        idempotency_key="seed:assert-region-b",
        event_id="evt-assert-region-b",
        correction_of="assert-region-a",
    )
    _source(
        service,
        source_id="source-runbook-003",
        title="Atlas runbook",
        text="Project Atlas on-call owner is Priya.",
        observed_at=datetime(2026, 10, 16, 11, 0, tzinfo=UTC),
        event_id="evt-source-runbook-003",
    )
    _assertion(
        service,
        assertion_id="assert-oncall-priya",
        predicate="oncall_owner",
        value="Priya",
        source_id="source-runbook-003",
        observed_at=datetime(2026, 10, 16, 11, 0, tzinfo=UTC),
        confidence=0.9,
        idempotency_key="seed:assert-oncall-priya",
        event_id="evt-assert-oncall-priya",
    )
    _source(
        service,
        source_id="source-slack-004",
        title="Atlas staffing note",
        text="Project Atlas on-call owner is Jordan.",
        observed_at=datetime(2026, 10, 16, 12, 0, tzinfo=UTC),
        event_id="evt-source-slack-004",
    )
    _assertion(
        service,
        assertion_id="assert-oncall-jordan",
        predicate="oncall_owner",
        value="Jordan",
        source_id="source-slack-004",
        observed_at=datetime(2026, 10, 16, 12, 0, tzinfo=UTC),
        confidence=0.9,
        idempotency_key="seed:assert-oncall-jordan",
        event_id="evt-assert-oncall-jordan",
    )


def _source(service: MemoryService, **kwargs: object) -> None:
    service.create_source(
        TENANT_ID,
        source_type="synthetic_doc",
        trust_tier="reviewed",
        session_id="session-atlas-seed",
        agent_id="agent-planner",
        **kwargs,  # type: ignore[arg-type]
    )


def _assertion(service: MemoryService, **kwargs: object) -> None:
    service.create_assertion(
        TENANT_ID,
        entity_id=ENTITY_ID,
        session_id="session-atlas-seed",
        agent_id="agent-planner",
        **kwargs,  # type: ignore[arg-type]
    )


def main() -> None:
    seed_atlas()


if __name__ == "__main__":
    main()
