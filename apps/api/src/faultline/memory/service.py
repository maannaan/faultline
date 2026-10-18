"""Write path for events, sources, assertions, and timeline reads."""

from __future__ import annotations

from datetime import datetime

from faultline.config import Settings
from faultline.constants import PREDICATES, SYSTEM_AGENT_ID, SYSTEM_SESSION_ID
from faultline.errors import FaultlineError
from faultline.graph import repository as repo
from faultline.graph.client import GraphStore
from faultline.logging import log_event
from faultline.memory.ids import content_hash, new_id, normalize_text, to_iso
from faultline.memory.policy import decide_assertion
from faultline.schemas.models import (
    AssertionResult,
    EntityOut,
    EventResult,
    SourceResult,
    TimelineItem,
    TimelineResponse,
)

_SUPERSEDE_REASON = "Superseded by a reviewed correction."


class MemoryService:
    def __init__(self, settings: Settings, store: GraphStore) -> None:
        self.settings = settings
        self.store = store

    def graph(self, tenant_id: str):
        return self.store.graph_for_tenant(tenant_id)

    def ensure_user(self, tenant_id: str, user_id: str) -> None:
        repo.ensure_user(self.graph(tenant_id), tenant_id, user_id)

    def ensure_agent(self, tenant_id: str, agent_id: str, role: str, version: str) -> None:
        repo.ensure_agent(self.graph(tenant_id), tenant_id, agent_id, role, version)

    def ensure_session(
        self,
        tenant_id: str,
        session_id: str,
        user_id: str,
        started_at: datetime,
    ) -> None:
        created = repo.ensure_session(
            self.graph(tenant_id),
            user_id,
            session_id,
            to_iso(started_at),
        )
        if not created:
            raise FaultlineError("validation_error", "User not found", 400)

    def ensure_entity(
        self,
        tenant_id: str,
        *,
        entity_id: str,
        canonical_name: str,
        entity_type: str,
    ) -> EntityOut:
        graph = self.graph(tenant_id)
        row = repo.merge_entity(
            graph,
            entity_id=entity_id,
            canonical_name=canonical_name.strip(),
            entity_type=entity_type.strip(),
            normalized_name=normalize_text(canonical_name),
            normalized_type=normalize_text(entity_type),
        )
        return EntityOut(
            entity_id=str(row["id"]),
            entity_type=str(row["entity_type"]),
            canonical_name=str(row["canonical_name"]),
        )

    def create_event(
        self,
        tenant_id: str,
        *,
        session_id: str,
        agent_id: str,
        event_type: str,
        observed_at: datetime,
        idempotency_key: str,
        event_id: str | None = None,
    ) -> tuple[EventResult, bool]:
        graph = self.graph(tenant_id)
        existing = repo.find_event_by_idempotency(graph, idempotency_key)
        if existing:
            return _event_result(existing), False
        if not repo.find_session(graph, session_id):
            raise FaultlineError("validation_error", "Session not found", 400)
        if not repo.find_agent(graph, agent_id):
            raise FaultlineError("validation_error", "Agent not found", 400)
        created = repo.insert_event(
            graph,
            event_id=event_id or new_id("evt"),
            event_type=event_type.strip(),
            observed_at=to_iso(observed_at),
            idempotency_key=idempotency_key,
            session_id=session_id,
            agent_id=agent_id,
        )
        if created is None:
            raise FaultlineError("validation_error", "Session or agent not found", 400)
        log_event("memory.event_written", assertion_id="", source_id="")
        return _event_result(created), True

    def create_source(
        self,
        tenant_id: str,
        *,
        source_type: str,
        trust_tier: str,
        observed_at: datetime,
        title: str,
        text: str,
        source_id: str | None = None,
        event_id: str | None = None,
        session_id: str | None = None,
        agent_id: str | None = None,
    ) -> tuple[SourceResult, bool]:
        self.validate_text(text)
        graph = self.graph(tenant_id)
        if source_id:
            existing = repo.find_source(graph, source_id)
            if existing:
                return _source_result(existing), False
        session = session_id or SYSTEM_SESSION_ID
        agent = agent_id or SYSTEM_AGENT_ID
        if not repo.find_session(graph, session):
            raise FaultlineError("validation_error", "Session not found", 400)
        if not repo.find_agent(graph, agent):
            raise FaultlineError("validation_error", "Agent not found", 400)
        source_key = source_id or new_id("src")
        event_key = event_id or new_id("evt")
        created = repo.insert_source(
            graph,
            source_id=source_key,
            source_type=source_type.strip(),
            trust_tier=trust_tier,
            observed_at=to_iso(observed_at),
            title=title.strip(),
            excerpt=text,
            content_hash=content_hash(text),
            event_id=event_key,
            event_idempotency_key=f"source-event:{source_key}",
            session_id=session,
            agent_id=agent,
        )
        if created is None:
            raise FaultlineError("validation_error", "Session or agent not found", 400)
        log_event("memory.event_written", source_id=source_key)
        return _source_result(created), True

    def create_assertion(
        self,
        tenant_id: str,
        *,
        predicate: str,
        value: str,
        source_id: str,
        observed_at: datetime,
        confidence: float,
        idempotency_key: str,
        entity_id: str | None = None,
        entity_name: str | None = None,
        entity_type: str | None = None,
        valid_from: datetime | None = None,
        valid_to: datetime | None = None,
        correction_of: str | None = None,
        assertion_id: str | None = None,
        event_id: str | None = None,
        session_id: str | None = None,
        agent_id: str | None = None,
    ) -> tuple[AssertionResult, bool]:
        if predicate not in PREDICATES:
            raise FaultlineError("validation_error", "Predicate is not allow-listed", 400)
        cleaned_value = value.strip()
        if not cleaned_value:
            raise FaultlineError("validation_error", "Value is required", 400)
        if not 0 <= confidence <= 1:
            raise FaultlineError("validation_error", "Confidence must be between 0 and 1", 400)
        observed = to_iso(observed_at)
        valid_from_iso = to_iso(valid_from) if valid_from else None
        valid_to_iso = to_iso(valid_to) if valid_to else None
        if valid_from_iso and valid_to_iso and valid_from_iso > valid_to_iso:
            raise FaultlineError(
                "validation_error",
                "valid_from must be at or before valid_to",
                400,
            )

        graph = self.graph(tenant_id)
        existing_id = repo.find_assertion_by_idempotency(graph, idempotency_key)
        if existing_id:
            return self._view(graph, existing_id), False

        source = repo.find_source(graph, source_id)
        if source is None:
            log_event("memory.source_missing", source_id=source_id)
            raise FaultlineError("validation_error", "Source not found", 400)

        if correction_of is not None and not correction_of.strip():
            correction_of = None
        target = None
        if correction_of:
            target = repo.find_assertion_brief(graph, correction_of)
            if target is None:
                raise FaultlineError(
                    "validation_error",
                    "correction_of assertion was not found",
                    400,
                )
            if entity_id and entity_id.strip() and entity_id.strip() != target["entity_id"]:
                raise FaultlineError(
                    "validation_error",
                    "correction_of must match the entity and predicate",
                    400,
                )
            if not (entity_id and entity_id.strip()):
                target_entity = repo.find_entity(graph, str(target["entity_id"]))
                names_match = (
                    target_entity is not None
                    and entity_name is not None
                    and entity_type is not None
                    and normalize_text(entity_name) == target_entity["normalized_name"]
                    and normalize_text(entity_type) == target_entity["normalized_type"]
                )
                if not names_match:
                    raise FaultlineError(
                        "validation_error",
                        "correction_of must match the entity and predicate",
                        400,
                    )
                entity_id = str(target["entity_id"])

        entity = self._resolve_entity(
            graph,
            entity_id=entity_id,
            entity_name=entity_name,
            entity_type=entity_type,
        )
        if target and (
            target["entity_id"] != entity["id"] or target["predicate"] != predicate
        ):
            raise FaultlineError(
                "validation_error",
                "correction_of must match the entity and predicate",
                400,
            )

        normalized_value = normalize_text(cleaned_value)
        duplicate_id = repo.find_semantic_duplicate(
            graph,
            entity_id=str(entity["id"]),
            predicate=predicate,
            value_normalized=normalized_value,
            source_id=source_id,
        )
        session = session_id or SYSTEM_SESSION_ID
        agent = agent_id or SYSTEM_AGENT_ID
        if duplicate_id:
            linked = repo.link_duplicate_event(
                graph,
                assertion_id=duplicate_id,
                source_id=source_id,
                entity_id=str(entity["id"]),
                event_id=event_id or new_id("evt"),
                observed_at=observed,
                idempotency_key=f"link:{idempotency_key}",
                session_id=session,
                agent_id=agent,
            )
            if not linked:
                raise FaultlineError("validation_error", "Session or agent not found", 400)
            return self._view(graph, duplicate_id), False

        priors = repo.list_active_claims(graph, str(entity["id"]), predicate)
        conflicts = [
            str(row["assertion_id"])
            for row in priors
            if str(row.get("trust_tier")) == "reviewed"
            and str(row.get("value_normalized")) != normalized_value
        ]
        decision = decide_assertion(
            trust_tier=str(source["trust_tier"]),
            correction_of=correction_of,
            conflicting_ids=conflicts,
        )
        new_assertion_id = assertion_id or new_id("assert")
        if repo.find_assertion_brief(graph, new_assertion_id):
            raise FaultlineError("validation_error", "Assertion id already exists", 400)
        origin_event_id = event_id or new_id("evt")
        inserted = repo.insert_assertion(
            graph,
            {
                "id": new_assertion_id,
                "predicate": predicate,
                "value": cleaned_value,
                "value_normalized": normalized_value,
                "status": decision.status,
                "observed_at": observed,
                "valid_from": valid_from_iso,
                "valid_to": valid_to_iso,
                "confidence": float(confidence),
                "policy_version": self.settings.policy_version,
                "resolution": decision.resolution,
                "resolution_reason": decision.resolution_reason,
                "idempotency_key": idempotency_key,
                "origin_event_id": origin_event_id,
                "entity_id": entity["id"],
                "source_id": source_id,
                "session_id": session,
                "agent_id": agent,
                "event_idempotency_key": f"assertion-event:{idempotency_key}",
            },
        )
        if inserted is None:
            raise FaultlineError("validation_error", "Session or agent not found", 400)
        if decision.supersede_id:
            repo.supersede(graph, inserted, decision.supersede_id, _SUPERSEDE_REASON)
            log_event(
                "memory.assertion_superseded",
                assertion_id=decision.supersede_id,
                source_id=source_id,
                status_value="superseded",
            )
        for other_id in decision.dispute_ids:
            repo.dispute(graph, inserted, other_id, decision.resolution_reason)
            log_event(
                "memory.conflict_detected",
                assertion_id=inserted,
                source_id=source_id,
                status_value="disputed",
            )
        log_event(
            "memory.assertion_accepted",
            assertion_id=inserted,
            source_id=source_id,
            status_value=decision.status,
        )
        return self._view(graph, inserted), True

    def list_entities(self, tenant_id: str) -> list[EntityOut]:
        rows = repo.list_entities(self.graph(tenant_id))
        return [
            EntityOut(
                entity_id=str(row["entity_id"]),
                entity_type=str(row["entity_type"]),
                canonical_name=str(row["canonical_name"]),
            )
            for row in rows
            if row.get("entity_id")
        ]

    def get_timeline(self, tenant_id: str, entity_id: str, limit: int = 100) -> TimelineResponse:
        bounded = min(max(limit, 1), 200)
        graph = self.graph(tenant_id)
        if not repo.entity_exists(graph, entity_id):
            raise FaultlineError("not_found", "Entity not found", 404)
        items = []
        for row in repo.timeline_rows(graph, entity_id, bounded):
            items.append(
                TimelineItem(
                    assertion_id=str(row["assertion_id"]),
                    predicate=str(row["predicate"]),
                    value=str(row["value"]),
                    status=str(row["status"]),
                    observed_at=str(row["observed_at"]),
                    valid_from=_optional_str(row.get("valid_from")),
                    valid_to=_optional_str(row.get("valid_to")),
                    confidence=float(row["confidence"]),
                    source_id=_optional_str(row.get("source_id")),
                    event_id=_optional_str(row.get("event_id")),
                    supersedes_ids=list(row["supersedes_ids"]),
                    conflicts_with_ids=list(row["conflicts_with_ids"]),
                    resolution=str(row["resolution"]),
                    resolution_reason=str(row["resolution_reason"]),
                    policy_version=str(row["policy_version"]),
                )
            )
        return TimelineResponse(
            entity_id=entity_id,
            policy_version=self.settings.policy_version,
            items=items,
        )

    def get_assertion(self, tenant_id: str, assertion_id: str) -> AssertionResult:
        return self._view(self.graph(tenant_id), assertion_id)

    def _resolve_entity(
        self,
        graph,
        *,
        entity_id: str | None,
        entity_name: str | None,
        entity_type: str | None,
    ) -> dict:
        if entity_id and entity_id.strip():
            found = repo.find_entity(graph, entity_id.strip())
            if found is None:
                raise FaultlineError("validation_error", "Entity not found", 400)
            return found
        if not entity_name or not entity_type:
            raise FaultlineError(
                "validation_error",
                "entity_id or entity_name and entity_type is required",
                400,
            )
        return repo.merge_entity(
            graph,
            entity_id=new_id("ent"),
            canonical_name=entity_name.strip(),
            entity_type=entity_type.strip(),
            normalized_name=normalize_text(entity_name),
            normalized_type=normalize_text(entity_type),
        )

    def _view(self, graph, assertion_id: str) -> AssertionResult:
        row = repo.assertion_view(graph, assertion_id)
        if row is None:
            raise FaultlineError("not_found", "Assertion not found", 404)
        source_id = _optional_str(row.get("source_id")) or ""
        entity_id = _optional_str(row.get("entity_id")) or ""
        return AssertionResult(
            assertion_id=str(row["assertion_id"]),
            status=str(row["status"]),
            policy_version=str(row["policy_version"]),
            resolution=str(row["resolution"]),
            superseded_ids=list(row["superseded_ids"]),
            evidence_path=[str(row["assertion_id"]), source_id, entity_id],
        )

    def validate_text(self, text: str) -> None:
        if len(text) > self.settings.max_note_chars:
            raise FaultlineError(
                "validation_error",
                f"Text exceeds {self.settings.max_note_chars} characters",
                400,
            )


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    if text == "" or text == "None":
        return None
    return text


def _event_result(row: dict) -> EventResult:
    return EventResult(
        event_id=str(row["event_id"]),
        event_type=str(row["event_type"]),
        observed_at=str(row["observed_at"]),
        idempotency_key=str(row["idempotency_key"]),
    )


def _source_result(row: dict) -> SourceResult:
    return SourceResult(
        source_id=str(row["source_id"]),
        event_id=str(row.get("event_id") or ""),
        trust_tier=str(row["trust_tier"]),
        content_hash=str(row["content_hash"]),
    )
