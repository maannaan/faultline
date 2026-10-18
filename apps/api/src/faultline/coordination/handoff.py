"""Copy snapshot conflicts onto a handoff. The client cannot omit them."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from faultline.config import Settings
from faultline.constants import STATUS_DISPUTED, TASK_QUEUED
from faultline.coordination.tasks import (
    require_version,
    transition_accept,
    transition_complete,
    transition_handoff,
    transition_revalidate,
)
from faultline.errors import FaultlineError
from faultline.graph import repository as repo
from faultline.graph.client import GraphStore
from faultline.logging import log_event
from faultline.memory.ids import new_id, to_iso
from faultline.memory.temporal import SnapshotMember
from faultline.schemas.models import ConflictOut, HandoffView, TaskCreated, TaskView


class CoordinationService:
    def __init__(self, settings: Settings, store: GraphStore) -> None:
        self.settings = settings
        self.store = store

    def create_task(
        self,
        tenant_id: str,
        *,
        objective: str,
        owner_agent_id: str,
        acceptance_criteria: list[str],
        idempotency_key: str,
    ) -> tuple[TaskCreated, bool]:
        graph = self.store.graph_for_tenant(tenant_id)
        existing = repo.find_task_id_by_idempotency(graph, idempotency_key)
        if existing:
            task = self._require_task(graph, existing)
            return _created(task), False
        if not repo.find_agent(graph, owner_agent_id):
            raise FaultlineError("validation_error", "Agent not found", 400)
        task_id = new_id("task")
        repo.insert_task(
            graph,
            {
                "id": task_id,
                "objective": objective.strip(),
                "status": TASK_QUEUED,
                "version": 1,
                "acceptance_criteria": json.dumps(acceptance_criteria),
                "idempotency_key": idempotency_key,
                "created_at": to_iso(datetime.now(UTC)),
                "owner_agent_id": owner_agent_id,
            },
        )
        log_event("coordination.task_created", assertion_id=task_id)
        task = self._require_task(graph, task_id)
        return _created(task), True

    def create_handoff(
        self,
        tenant_id: str,
        task_id: str,
        *,
        to_agent_id: str,
        snapshot_id: str,
        memory_refs: list[str],
        expected_version: int,
        idempotency_key: str,
        open_questions: list[str],
        expires_at: datetime,
    ) -> tuple[TaskView, bool]:
        graph = self.store.graph_for_tenant(tenant_id)
        existing = repo.find_handoff_task_id(graph, idempotency_key)
        if existing:
            return self._view(graph, existing), False
        task = self._require_task(graph, task_id)
        require_version(task.version, expected_version)
        status = transition_handoff(task.status)
        if not repo.find_agent(graph, to_agent_id):
            raise FaultlineError("validation_error", "Agent not found", 400)
        members = _snapshot_members(graph, snapshot_id)
        refs = _checked_refs(memory_refs, members)
        conflicts = [member.assertion_id for member in members if member.status == STATUS_DISPUTED]
        repo.insert_handoff(
            graph,
            {
                "id": new_id("handoff"),
                "task_id": task_id,
                "from_agent_id": task.owner_agent_id,
                "to_agent_id": to_agent_id,
                "snapshot_id": snapshot_id,
                "open_questions": json.dumps(open_questions),
                "expires_at": to_iso(expires_at),
                "idempotency_key": idempotency_key,
                "created_at": to_iso(datetime.now(UTC)),
                "status": status,
                "version": task.version + 1,
                "memory_refs": refs,
                "conflict_ids": conflicts,
            },
        )
        log_event("coordination.handoff_created", assertion_id=task_id)
        return self._view(graph, task_id), True

    def get_task(self, tenant_id: str, task_id: str) -> TaskView:
        graph = self.store.graph_for_tenant(tenant_id)
        return self._view(graph, task_id)

    def accept(
        self,
        tenant_id: str,
        task_id: str,
        *,
        agent_id: str,
        expected_version: int,
    ) -> TaskView:
        graph = self.store.graph_for_tenant(tenant_id)
        task = self._require_task(graph, task_id)
        require_version(task.version, expected_version)
        if task.handoff is None:
            raise FaultlineError("validation_error", "Task has no handoff", 400)
        status = transition_accept(task.status, agent_id, task.handoff.to_agent_id)
        if not repo.find_agent(graph, agent_id):
            raise FaultlineError("validation_error", "Agent not found", 400)
        repo.set_task_owner(graph, task_id, agent_id, status, task.version + 1)
        log_event("coordination.handoff_accepted", assertion_id=task_id)
        return self._view(graph, task_id)

    def complete(
        self,
        tenant_id: str,
        task_id: str,
        *,
        expected_version: int,
        result: str,
        evidence_refs: list[str],
    ) -> TaskView:
        graph = self.store.graph_for_tenant(tenant_id)
        task = self._require_task(graph, task_id)
        require_version(task.version, expected_version)
        if task.handoff is None:
            raise FaultlineError("validation_error", "Task has no handoff", 400)
        if task.handoff.stale:
            reason = task.handoff.stale_reason or "Snapshot is stale"
            raise FaultlineError("snapshot_stale", reason, 409)
        next_status = transition_complete(task.status)
        allowed = set(task.handoff.memory_refs)
        allowed.update(item.assertion_id for item in task.handoff.unresolved_conflicts)
        if any(ref not in allowed for ref in evidence_refs):
            raise FaultlineError(
                "validation_error",
                "Evidence reference is not on the handoff",
                400,
            )
        repo.complete_task(
            graph,
            task_id,
            status=next_status,
            version=task.version + 1,
            result=result.strip(),
            evidence_refs=json.dumps(evidence_refs),
        )
        log_event("coordination.task_completed", assertion_id=task_id)
        return self._view(graph, task_id)

    def revalidate(
        self,
        tenant_id: str,
        task_id: str,
        *,
        expected_version: int,
        snapshot_id: str,
        expires_at: datetime | None,
    ) -> TaskView:
        graph = self.store.graph_for_tenant(tenant_id)
        task = self._require_task(graph, task_id)
        require_version(task.version, expected_version)
        if task.handoff is None:
            raise FaultlineError("validation_error", "Task has no handoff", 400)
        transition_revalidate(task.status)
        members = _snapshot_members(graph, snapshot_id)
        conflicts = [member.assertion_id for member in members if member.status == STATUS_DISPUTED]
        repo.replace_handoff_snapshot(
            graph,
            task_id=task_id,
            handoff_id=task.handoff.handoff_id,
            snapshot_id=snapshot_id,
            conflict_ids=conflicts,
            version=task.version + 1,
            expires_at=to_iso(expires_at) if expires_at else None,
        )
        log_event("coordination.handoff_revalidated", assertion_id=task_id)
        return self._view(graph, task_id)

    def _require_task(self, graph, task_id: str) -> TaskView:
        return self._view(graph, task_id)

    def _view(self, graph, task_id: str) -> TaskView:
        row = repo.load_task(graph, task_id)
        if row is None:
            raise FaultlineError("not_found", "Task not found", 404)
        handoff = None
        if row.get("handoff_id"):
            members = _snapshot_members(graph, str(row["snapshot_id"]))
            predicates = _predicates_for_refs(list(row["memory_refs"]), members)
            stale, reason = _stale(graph, row, predicates)
            handoff = HandoffView(
                handoff_id=str(row["handoff_id"]),
                snapshot_id=str(row["snapshot_id"]),
                memory_refs=list(row["memory_refs"]),
                unresolved_conflicts=[
                    ConflictOut(
                        assertion_id=str(item["assertion_id"]),
                        predicate=str(item["predicate"]),
                        value=str(item["value"]),
                        source_id=_optional(item.get("source_id")),
                    )
                    for item in row["conflicts"]
                    if item.get("assertion_id")
                ],
                stale=stale,
                stale_reason=reason,
                from_agent_id=str(row["from_agent_id"]),
                to_agent_id=str(row["to_agent_id"]),
                expires_at=str(row["expires_at"]),
                open_questions=_json_list(row.get("open_questions")),
                result=_optional(row.get("result")),
                evidence_refs=_json_list(row.get("evidence_refs")),
            )
        return TaskView(
            task_id=str(row["task_id"]),
            objective=str(row["objective"]),
            status=str(row["status"]),
            version=int(row["version"]),
            owner_agent_id=str(row["owner_agent_id"]),
            acceptance_criteria=_json_list(row.get("acceptance_criteria")),
            handoff=handoff,
        )


def _created(task: TaskView) -> TaskCreated:
    return TaskCreated(
        task_id=task.task_id,
        status=task.status,
        version=task.version,
        owner_agent_id=task.owner_agent_id,
    )


def _snapshot_members(graph, snapshot_id: str) -> list[SnapshotMember]:
    raw = repo.load_snapshot(graph, snapshot_id)
    if raw is None:
        raise FaultlineError("not_found", "Snapshot not found", 404)
    members: list[SnapshotMember] = []
    for row in raw["rows"]:
        if not row.get("assertion_id"):
            continue
        members.append(
            SnapshotMember(
                assertion_id=str(row["assertion_id"]),
                predicate=str(row["assertion_predicate"]),
                value=str(row["value"]),
                status=str(row["status"]),
                observed_at=str(row["observed_at"]),
                valid_from=_optional(row.get("valid_from")),
                valid_to=_optional(row.get("valid_to")),
                confidence=float(row["confidence"] or 0),
                source_id=str(row.get("source_id") or ""),
                event_id=_optional(row.get("event_id")),
                supersedes_ids=tuple(_json_list(row.get("supersedes_ids"))),
                conflicts_with_ids=tuple(_json_list(row.get("conflicts_with_ids"))),
                reason=str(row.get("reason") or ""),
            )
        )
    return members


def _checked_refs(memory_refs: list[str], members: list[SnapshotMember]) -> list[dict[str, str]]:
    assertions = {member.assertion_id for member in members}
    sources = {member.source_id for member in members if member.source_id}
    checked: list[dict[str, str]] = []
    seen: set[str] = set()
    for ref in memory_refs:
        cleaned = ref.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        if cleaned in assertions:
            checked.append({"id": cleaned, "kind": "assertion"})
        elif cleaned in sources:
            checked.append({"id": cleaned, "kind": "source"})
        else:
            raise FaultlineError(
                "reference_not_in_snapshot",
                "A memory reference is not in the snapshot",
                400,
            )
    if not checked:
        raise FaultlineError("validation_error", "memory_refs is required", 400)
    return checked


def _predicates_for_refs(refs: list[str], members: list[SnapshotMember]) -> set[str]:
    predicates: set[str] = set()
    for ref in refs:
        for member in members:
            if member.assertion_id == ref or member.source_id == ref:
                predicates.add(member.predicate)
    return predicates


def _stale(graph, row: dict, predicates: set[str]) -> tuple[bool, str | None]:
    now = to_iso(datetime.now(UTC))
    if str(row.get("expires_at") or "") < now:
        return True, "The handoff has expired."
    entities = set(row.get("entity_ids") or [])
    if not predicates or not entities:
        return False, None
    for item in repo.newer_memory(graph, str(row["as_of_time"])):
        if str(item.get("entity_id")) in entities and str(item.get("predicate")) in predicates:
            return True, "A newer assertion was recorded after the snapshot cutoff."
    return False, None


def _json_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    text = str(value)
    if text in ("", "None"):
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return [text]
    if isinstance(parsed, list):
        return [str(item) for item in parsed if item]
    return []


def _optional(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    if text in ("", "None"):
        return None
    return text
