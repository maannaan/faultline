"""HTTP routes."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response

from faultline.auth import require_tenant
from faultline.bench.ablation import run_ablation
from faultline.coordination.handoff import CoordinationService
from faultline.graph.subgraph import build_graph_view
from faultline.memory.ingest import ingest_note
from faultline.memory.service import MemoryService
from faultline.replay.bisect import run_bisect
from faultline.replay.service import LabService
from faultline.schemas.models import (
    AblationReport,
    AcceptCreate,
    AssertionCreate,
    AssertionResult,
    BisectCreate,
    BisectResult,
    CompleteCreate,
    EntityList,
    EventCreate,
    EventResult,
    EvidencePath,
    GraphView,
    HandoffCreate,
    HealthResponse,
    NoteCreate,
    NoteIngestResult,
    ReplayCreate,
    ReplayDiff,
    ReplayResult,
    RevalidateCreate,
    SnapshotCreate,
    SnapshotResult,
    SourceCreate,
    SourceResult,
    TaskCreate,
    TaskCreated,
    TaskView,
    TimelineResponse,
)

router = APIRouter()


def get_service(request: Request) -> MemoryService:
    return MemoryService(request.app.state.settings, request.app.state.store)


def get_coordination(request: Request) -> CoordinationService:
    return CoordinationService(request.app.state.settings, request.app.state.store)


def get_lab(request: Request) -> LabService:
    return LabService(
        request.app.state.settings,
        request.app.state.store,
        request.app.state.answerer,
    )


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.post("/v1/benchmarks/ablation", response_model=AblationReport)
def post_ablation(
    request: Request,
    tenant_id: Annotated[str, Depends(require_tenant)],
) -> AblationReport:
    return run_ablation(request.app.state.settings, request.app.state.store, tenant_id)


@router.get("/health/ready", response_model=HealthResponse)
def ready(request: Request) -> HealthResponse:
    request.app.state.store.ping()
    return HealthResponse(status="ok")


@router.post("/v1/events", response_model=EventResult)
def post_event(
    body: EventCreate,
    response: Response,
    tenant_id: Annotated[str, Depends(require_tenant)],
    service: Annotated[MemoryService, Depends(get_service)],
) -> EventResult:
    result, created = service.create_event(
        tenant_id,
        session_id=body.session_id,
        agent_id=body.agent_id,
        event_type=body.event_type,
        observed_at=body.observed_at,
        idempotency_key=body.idempotency_key,
    )
    response.status_code = 201 if created else 200
    return result


@router.post("/v1/sources", response_model=SourceResult)
def post_source(
    body: SourceCreate,
    response: Response,
    tenant_id: Annotated[str, Depends(require_tenant)],
    service: Annotated[MemoryService, Depends(get_service)],
) -> SourceResult:
    result, created = service.create_source(
        tenant_id,
        source_type=body.source_type,
        trust_tier=body.trust_tier,
        observed_at=body.observed_at,
        title=body.title,
        text=body.text,
    )
    response.status_code = 201 if created else 200
    return result


@router.post("/v1/assertions", response_model=AssertionResult)
def post_assertion(
    body: AssertionCreate,
    response: Response,
    tenant_id: Annotated[str, Depends(require_tenant)],
    service: Annotated[MemoryService, Depends(get_service)],
) -> AssertionResult:
    result, created = service.create_assertion(
        tenant_id,
        entity_id=body.entity_id,
        entity_name=body.entity_name,
        entity_type=body.entity_type,
        predicate=body.predicate,
        value=body.value,
        source_id=body.source_id,
        observed_at=body.observed_at,
        valid_from=body.valid_from,
        valid_to=body.valid_to,
        confidence=body.confidence,
        idempotency_key=body.idempotency_key,
        correction_of=body.correction_of,
    )
    response.status_code = 201 if created else 200
    return result


@router.get("/v1/assertions/{assertion_id}", response_model=AssertionResult)
def get_assertion(
    assertion_id: str,
    tenant_id: Annotated[str, Depends(require_tenant)],
    service: Annotated[MemoryService, Depends(get_service)],
) -> AssertionResult:
    return service.get_assertion(tenant_id, assertion_id)


@router.get("/v1/assertions/{assertion_id}/evidence", response_model=EvidencePath)
def get_evidence(
    assertion_id: str,
    tenant_id: Annotated[str, Depends(require_tenant)],
    lab: Annotated[LabService, Depends(get_lab)],
) -> EvidencePath:
    return lab.evidence(tenant_id, assertion_id)


@router.post("/v1/snapshots", response_model=SnapshotResult)
def post_snapshot(
    body: SnapshotCreate,
    response: Response,
    tenant_id: Annotated[str, Depends(require_tenant)],
    lab: Annotated[LabService, Depends(get_lab)],
) -> SnapshotResult:
    result, created = lab.create_snapshot(
        tenant_id,
        as_of_time=body.as_of_time,
        time_mode=body.time_mode,
        entity_ids=body.entity_ids,
        predicate=body.predicate,
        exclude_source_ids=body.exclude_source_ids,
        idempotency_key=body.idempotency_key,
    )
    response.status_code = 201 if created else 200
    return result


@router.get("/v1/snapshots/{snapshot_id}", response_model=SnapshotResult)
def get_snapshot(
    snapshot_id: str,
    tenant_id: Annotated[str, Depends(require_tenant)],
    lab: Annotated[LabService, Depends(get_lab)],
) -> SnapshotResult:
    return lab.get_snapshot(tenant_id, snapshot_id)


@router.post("/v1/replays", response_model=ReplayResult)
def post_replay(
    body: ReplayCreate,
    response: Response,
    tenant_id: Annotated[str, Depends(require_tenant)],
    lab: Annotated[LabService, Depends(get_lab)],
) -> ReplayResult:
    result, created = lab.create_replay(
        tenant_id,
        question=body.question,
        predicate=body.predicate,
        snapshot_id=body.snapshot_id,
        idempotency_key=body.idempotency_key,
    )
    response.status_code = 201 if created else 200
    return result


@router.get("/v1/replays/{replay_id}/diff", response_model=ReplayDiff)
def get_replay_diff(
    replay_id: str,
    baseline_replay_id: Annotated[str, Query(min_length=1)],
    tenant_id: Annotated[str, Depends(require_tenant)],
    lab: Annotated[LabService, Depends(get_lab)],
) -> ReplayDiff:
    return lab.diff_replays(tenant_id, replay_id, baseline_replay_id)


@router.get("/v1/entities", response_model=EntityList)
def get_entities(
    tenant_id: Annotated[str, Depends(require_tenant)],
    service: Annotated[MemoryService, Depends(get_service)],
) -> EntityList:
    return EntityList(entities=service.list_entities(tenant_id))


@router.get("/v1/timeline", response_model=TimelineResponse)
def get_timeline(
    tenant_id: Annotated[str, Depends(require_tenant)],
    service: Annotated[MemoryService, Depends(get_service)],
    entity_id: Annotated[str, Query(min_length=1)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> TimelineResponse:
    return service.get_timeline(tenant_id, entity_id, limit)


@router.get("/v1/graph", response_model=GraphView)
def get_graph(
    request: Request,
    tenant_id: Annotated[str, Depends(require_tenant)],
    entity_id: Annotated[str, Query(min_length=1)],
    as_of: datetime | None = None,
    time_mode: str = "known",
    exclude_source_ids: Annotated[str, Query(max_length=1000)] = "",
) -> GraphView:
    graph = request.app.state.store.graph_for_tenant(tenant_id)
    excluded = [item.strip() for item in exclude_source_ids.split(",") if item.strip()]
    return build_graph_view(
        graph,
        entity_id=entity_id,
        as_of=as_of,
        time_mode=time_mode,
        exclude_source_ids=excluded,
    )


@router.post("/v1/bisect", response_model=BisectResult)
def post_bisect(
    body: BisectCreate,
    request: Request,
    tenant_id: Annotated[str, Depends(require_tenant)],
) -> BisectResult:
    graph = request.app.state.store.graph_for_tenant(tenant_id)
    return run_bisect(
        graph,
        entity_id=body.entity_id,
        predicate=body.predicate,
        good_as_of=body.good_as_of,
        bad_as_of=body.bad_as_of,
        time_mode=body.time_mode,
    )


@router.post("/v1/notes", response_model=NoteIngestResult, status_code=201)
def post_note(
    body: NoteCreate,
    request: Request,
    tenant_id: Annotated[str, Depends(require_tenant)],
    service: Annotated[MemoryService, Depends(get_service)],
) -> NoteIngestResult:
    return ingest_note(
        service,
        tenant_id,
        text=body.text,
        trust_tier=body.trust_tier,
        observed_at=body.observed_at,
        session_id=body.session_id,
        agent_id=body.agent_id,
        extractor=request.app.state.extractor,
    )


@router.post("/v1/tasks", response_model=TaskCreated)
def post_task(
    body: TaskCreate,
    response: Response,
    tenant_id: Annotated[str, Depends(require_tenant)],
    coordination: Annotated[CoordinationService, Depends(get_coordination)],
) -> TaskCreated:
    result, created = coordination.create_task(
        tenant_id,
        objective=body.objective,
        owner_agent_id=body.owner_agent_id,
        acceptance_criteria=body.acceptance_criteria,
        idempotency_key=body.idempotency_key,
    )
    response.status_code = 201 if created else 200
    return result


@router.get("/v1/tasks/{task_id}", response_model=TaskView)
def get_task(
    task_id: str,
    tenant_id: Annotated[str, Depends(require_tenant)],
    coordination: Annotated[CoordinationService, Depends(get_coordination)],
) -> TaskView:
    return coordination.get_task(tenant_id, task_id)


@router.post("/v1/tasks/{task_id}/handoff", response_model=TaskView)
def post_handoff(
    task_id: str,
    body: HandoffCreate,
    response: Response,
    tenant_id: Annotated[str, Depends(require_tenant)],
    coordination: Annotated[CoordinationService, Depends(get_coordination)],
) -> TaskView:
    result, created = coordination.create_handoff(
        tenant_id,
        task_id,
        to_agent_id=body.to_agent_id,
        snapshot_id=body.snapshot_id,
        memory_refs=body.memory_refs,
        expected_version=body.expected_version,
        idempotency_key=body.idempotency_key,
        open_questions=body.open_questions,
        expires_at=body.expires_at,
    )
    response.status_code = 201 if created else 200
    return result


@router.post("/v1/tasks/{task_id}/accept", response_model=TaskView)
def post_accept(
    task_id: str,
    body: AcceptCreate,
    tenant_id: Annotated[str, Depends(require_tenant)],
    coordination: Annotated[CoordinationService, Depends(get_coordination)],
) -> TaskView:
    return coordination.accept(
        tenant_id,
        task_id,
        agent_id=body.agent_id,
        expected_version=body.expected_version,
    )


@router.post("/v1/tasks/{task_id}/complete", response_model=TaskView)
def post_complete(
    task_id: str,
    body: CompleteCreate,
    tenant_id: Annotated[str, Depends(require_tenant)],
    coordination: Annotated[CoordinationService, Depends(get_coordination)],
) -> TaskView:
    return coordination.complete(
        tenant_id,
        task_id,
        expected_version=body.expected_version,
        result=body.result,
        evidence_refs=body.evidence_refs,
    )


@router.post("/v1/tasks/{task_id}/revalidate", response_model=TaskView)
def post_revalidate(
    task_id: str,
    body: RevalidateCreate,
    tenant_id: Annotated[str, Depends(require_tenant)],
    coordination: Annotated[CoordinationService, Depends(get_coordination)],
) -> TaskView:
    return coordination.revalidate(
        tenant_id,
        task_id,
        expected_version=body.expected_version,
        snapshot_id=body.snapshot_id,
        expires_at=body.expires_at,
    )
