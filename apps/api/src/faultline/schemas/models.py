"""Request and response models. Clients cannot send status or tenant id."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return value.astimezone(UTC)


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EventCreate(APIModel):
    session_id: str = Field(min_length=1, max_length=200)
    agent_id: str = Field(min_length=1, max_length=200)
    event_type: str = Field(min_length=1, max_length=100)
    observed_at: datetime
    idempotency_key: str = Field(min_length=1, max_length=300)

    @field_validator("observed_at")
    @classmethod
    def _observed(cls, value: datetime) -> datetime:
        return ensure_aware(value)


class EventResult(BaseModel):
    event_id: str
    event_type: str
    observed_at: str
    idempotency_key: str


class SourceCreate(APIModel):
    source_type: str = Field(min_length=1, max_length=100)
    trust_tier: Literal["reviewed", "unreviewed"]
    observed_at: datetime
    title: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=1)

    @field_validator("observed_at")
    @classmethod
    def _observed(cls, value: datetime) -> datetime:
        return ensure_aware(value)


class SourceResult(BaseModel):
    source_id: str
    event_id: str
    trust_tier: str
    content_hash: str


class AssertionCreate(APIModel):
    entity_id: str | None = Field(default=None, max_length=200)
    entity_name: str | None = Field(default=None, max_length=300)
    entity_type: str | None = Field(default=None, max_length=100)
    predicate: str = Field(min_length=1, max_length=100)
    value: str = Field(min_length=1, max_length=500)
    source_id: str = Field(min_length=1, max_length=200)
    observed_at: datetime
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    confidence: float = Field(ge=0, le=1)
    idempotency_key: str = Field(min_length=1, max_length=300)
    correction_of: str | None = Field(default=None, max_length=200)

    @field_validator("observed_at", "valid_from", "valid_to")
    @classmethod
    def _times(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return ensure_aware(value)

    @model_validator(mode="after")
    def _entity_and_interval(self) -> AssertionCreate:
        has_id = bool(self.entity_id and self.entity_id.strip())
        has_name = bool(self.entity_name and self.entity_name.strip()) and bool(
            self.entity_type and self.entity_type.strip()
        )
        if not has_id and not has_name:
            raise ValueError("entity_id or entity_name and entity_type is required")
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            raise ValueError("valid_from must be at or before valid_to")
        return self


class AssertionResult(BaseModel):
    assertion_id: str
    status: str
    policy_version: str
    resolution: str
    superseded_ids: list[str]
    evidence_path: list[str]


class EntityOut(BaseModel):
    entity_id: str
    entity_type: str
    canonical_name: str


class EntityList(BaseModel):
    entities: list[EntityOut]


class TimelineItem(BaseModel):
    assertion_id: str
    predicate: str
    value: str
    status: str
    observed_at: str
    valid_from: str | None = None
    valid_to: str | None = None
    confidence: float
    source_id: str | None = None
    event_id: str | None = None
    supersedes_ids: list[str]
    conflicts_with_ids: list[str]
    resolution: str
    resolution_reason: str
    policy_version: str


class TimelineResponse(BaseModel):
    entity_id: str
    policy_version: str
    items: list[TimelineItem]


class NoteCreate(APIModel):
    text: str = Field(min_length=1)
    trust_tier: Literal["reviewed", "unreviewed"]
    observed_at: datetime
    session_id: str = Field(min_length=1, max_length=200)
    agent_id: str = Field(min_length=1, max_length=200)

    @field_validator("observed_at")
    @classmethod
    def _observed(cls, value: datetime) -> datetime:
        return ensure_aware(value)


class NoteIngestResult(BaseModel):
    source_id: str
    event_id: str
    extraction_status: Literal["completed", "failed"]
    extraction_error: str | None = None
    warnings: list[str] = Field(default_factory=list)
    assertions: list[AssertionResult]


class ProposedAssertion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_name: str
    entity_type: str
    predicate: str
    value: str
    valid_from: str | None = None
    valid_to: str | None = None
    confidence: float
    correction_of: str | None = None


class ExtractionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assertions: list[ProposedAssertion]


class HealthResponse(BaseModel):
    status: str


class SnapshotCreate(APIModel):
    as_of_time: datetime
    time_mode: Literal["known", "valid"]
    entity_ids: list[str] = Field(min_length=1, max_length=20)
    predicate: str | None = Field(default=None, max_length=100)
    exclude_source_ids: list[str] = Field(default_factory=list, max_length=20)
    idempotency_key: str = Field(min_length=1, max_length=300)

    @field_validator("as_of_time")
    @classmethod
    def _as_of(cls, value: datetime) -> datetime:
        return ensure_aware(value)

    @field_validator("entity_ids", "exclude_source_ids")
    @classmethod
    def _ids(cls, values: list[str]) -> list[str]:
        cleaned = [item.strip() for item in values if item and item.strip()]
        if values and not cleaned:
            raise ValueError("ids must not be blank")
        return cleaned

    @model_validator(mode="after")
    def _entities_present(self) -> SnapshotCreate:
        if not self.entity_ids:
            raise ValueError("entity_ids is required")
        return self


class SnapshotMemberOut(BaseModel):
    assertion_id: str
    predicate: str
    value: str
    status: str
    observed_at: str
    valid_from: str | None = None
    valid_to: str | None = None
    confidence: float
    source_id: str | None = None
    event_id: str | None = None
    supersedes_ids: list[str]
    conflicts_with_ids: list[str]
    reason: str


class SnapshotResult(BaseModel):
    snapshot_id: str
    as_of_time: str
    time_mode: str
    policy_version: str
    included: list[SnapshotMemberOut]
    validity_unknown_ids: list[str]


class EvidencePath(BaseModel):
    assertion_id: str
    source_id: str | None = None
    event_id: str | None = None
    session_id: str | None = None
    entity_id: str
    status: str
    supersedes_ids: list[str]
    conflicts_with_ids: list[str]


class ReplayCreate(APIModel):
    question: str = Field(min_length=1, max_length=1000)
    predicate: str = Field(min_length=1, max_length=100)
    snapshot_id: str = Field(min_length=1, max_length=200)
    idempotency_key: str = Field(min_length=1, max_length=300)


class ClaimOut(BaseModel):
    claim_id: str
    predicate: str
    value: str | None = None
    status: str
    evidence_ids: list[str]
    wording: str


class ReplayResult(BaseModel):
    replay_id: str
    snapshot_id: str
    claims: list[ClaimOut]
    model_version: str
    prompt_version: str
    citation_rejected: bool


class StatusChange(BaseModel):
    assertion_id: str
    from_status: str
    to_status: str


class ReplayDiff(BaseModel):
    baseline_replay_id: str
    candidate_replay_id: str
    added: list[str]
    removed: list[str]
    unchanged: list[str]
    status_changed: list[StatusChange]
    added_source_ids: list[str]
    removed_source_ids: list[str]
    answer_change: str
    explanation: str


class TaskCreate(APIModel):
    objective: str = Field(min_length=1, max_length=500)
    owner_agent_id: str = Field(min_length=1, max_length=200)
    acceptance_criteria: list[str] = Field(min_length=1, max_length=20)
    idempotency_key: str = Field(min_length=1, max_length=300)


class TaskCreated(BaseModel):
    task_id: str
    status: str
    version: int
    owner_agent_id: str


class HandoffCreate(APIModel):
    to_agent_id: str = Field(min_length=1, max_length=200)
    snapshot_id: str = Field(min_length=1, max_length=200)
    memory_refs: list[str] = Field(min_length=1, max_length=20)
    expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=1, max_length=300)
    open_questions: list[str] = Field(default_factory=list, max_length=20)
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def _expires(cls, value: datetime) -> datetime:
        return ensure_aware(value)


class ConflictOut(BaseModel):
    assertion_id: str
    predicate: str
    value: str
    source_id: str | None = None


class HandoffView(BaseModel):
    handoff_id: str
    snapshot_id: str
    memory_refs: list[str]
    unresolved_conflicts: list[ConflictOut]
    stale: bool
    stale_reason: str | None = None
    from_agent_id: str
    to_agent_id: str
    expires_at: str
    open_questions: list[str]
    result: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)


class TaskView(BaseModel):
    task_id: str
    objective: str
    status: str
    version: int
    owner_agent_id: str
    acceptance_criteria: list[str]
    handoff: HandoffView | None = None


class AcceptCreate(APIModel):
    agent_id: str = Field(min_length=1, max_length=200)
    expected_version: int = Field(ge=1)


class CompleteCreate(APIModel):
    expected_version: int = Field(ge=1)
    result: str = Field(min_length=1, max_length=1000)
    evidence_refs: list[str] = Field(min_length=1, max_length=20)


class RevalidateCreate(APIModel):
    expected_version: int = Field(ge=1)
    snapshot_id: str = Field(min_length=1, max_length=200)
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def _expires(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return ensure_aware(value)


class IncludedFact(BaseModel):
    assertion_id: str
    status: str
    value: str


class BenchClaim(BaseModel):
    status: str
    value: str | None = None
    evidence_ids: list[str]
    included: list[IncludedFact]


class AblationReport(BaseModel):
    intact: BenchClaim
    support_deleted: BenchClaim
    supersedes_deleted: BenchClaim
    restored: bool


class GraphNode(BaseModel):
    id: str
    kind: Literal["entity", "assertion", "source", "event", "session", "agent"]
    label: str
    sublabel: str = ""
    status: str | None = None
    status_now: str | None = None
    observed_at: str | None = None
    excluded: bool = False
    visible: bool


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    visible: bool


class GraphView(BaseModel):
    entity_id: str
    as_of: str
    time_mode: str
    moments: list[str]
    validity_unknown_ids: list[str]
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class BisectCreate(APIModel):
    entity_id: str = Field(min_length=1, max_length=200)
    predicate: str = Field(min_length=1, max_length=100)
    good_as_of: datetime
    bad_as_of: datetime
    time_mode: Literal["known", "valid"] = "known"

    @field_validator("good_as_of", "bad_as_of")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        return ensure_aware(value)


class BisectProbe(BaseModel):
    as_of: str
    status: str
    value: str | None = None
    evidence_ids: list[str]
    verdict: Literal["good", "bad"]


class BisectResult(BaseModel):
    entity_id: str
    predicate: str
    good: BisectProbe
    bad: BisectProbe
    flipped: bool
    candidates: int
    probes: list[BisectProbe]
    first_bad_as_of: str | None = None
    culprit_assertion_ids: list[str]
    culprit_source_ids: list[str]
    culprit_event_ids: list[str]
    explanation: str


class ImpactAssertion(BaseModel):
    assertion_id: str
    predicate: str
    value: str
    status_now: str
    superseded_by: list[str]
    conflicts_with: list[str]


class ImpactSnapshot(BaseModel):
    snapshot_id: str
    as_of: str
    status_then: str
    outdated: bool
    replay_count: int
    handoff_count: int


class ImpactReplay(BaseModel):
    replay_id: str
    question: str
    snapshot_id: str
    as_of: str
    claim_status: str
    claim_value: str | None = None
    status_then: str
    outdated: bool


class ImpactHandoff(BaseModel):
    handoff_id: str
    task_id: str
    objective: str
    task_status: str
    snapshot_id: str
    as_of: str
    status_then: str
    referenced: bool
    carried_as_conflict: bool
    outdated: bool


class ImpactReport(BaseModel):
    assertion: ImpactAssertion
    snapshots: list[ImpactSnapshot]
    replays: list[ImpactReplay]
    handoffs: list[ImpactHandoff]
    outdated_count: int
    summary: str
