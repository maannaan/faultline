"""Persist snapshots and replays. Historical status is stored on the inclusion edge."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Protocol

from faultline.config import Settings
from faultline.constants import PREDICATES
from faultline.errors import FaultlineError
from faultline.graph import repository as repo
from faultline.graph.client import GraphStore
from faultline.logging import log_event
from faultline.memory.ids import new_id, to_iso
from faultline.memory.temporal import (
    TIME_KNOWN,
    TIME_VALID,
    ObservedAssertion,
    SnapshotMember,
    classify_snapshot,
)
from faultline.replay.answer import (
    PROMPT_VERSION,
    AnswerClaimDraft,
    validate_claims,
)
from faultline.replay.diff import evidence_diff
from faultline.schemas.models import (
    ClaimOut,
    EvidencePath,
    ReplayDiff,
    ReplayResult,
    SnapshotMemberOut,
    SnapshotResult,
    StatusChange,
)

_MAX_INCLUDED = 50


class Answerer(Protocol):
    model_version: str

    def answer(
        self,
        question: str,
        predicate: str,
        members: list[SnapshotMember],
    ) -> list[AnswerClaimDraft]:
        """Return claims. The service rejects citations outside the snapshot."""


class LabService:
    def __init__(self, settings: Settings, store: GraphStore, answerer: Answerer) -> None:
        self.settings = settings
        self.store = store
        self.answerer = answerer

    def create_snapshot(
        self,
        tenant_id: str,
        *,
        as_of_time: datetime,
        time_mode: str,
        entity_ids: list[str],
        predicate: str | None,
        exclude_source_ids: list[str],
        idempotency_key: str,
    ) -> tuple[SnapshotResult, bool]:
        if time_mode not in (TIME_KNOWN, TIME_VALID):
            raise FaultlineError("validation_error", "time_mode must be known or valid", 400)
        if predicate is not None and predicate not in PREDICATES:
            raise FaultlineError("validation_error", "Predicate is not allow-listed", 400)
        graph = self.store.graph_for_tenant(tenant_id)
        existing = repo.find_snapshot_id_by_idempotency(graph, idempotency_key)
        if existing:
            return self._snapshot_result(graph, existing), False
        entities = _unique(entity_ids)
        excluded = _unique(exclude_source_ids)
        for entity_id in entities:
            if not repo.entity_exists(graph, entity_id):
                raise FaultlineError("validation_error", "Entity not found", 400)
        for source_id in excluded:
            if repo.find_source(graph, source_id) is None:
                raise FaultlineError("validation_error", "Source not found", 400)
        as_of = to_iso(as_of_time)
        rows = [
            row
            for entity_id in entities
            for row in repo.observed_assertions_for_entity(graph, entity_id, as_of)
        ]
        rows.sort(key=lambda row: str(row["observed_at"]))
        observed = [
            _observed(row)
            for row in rows
            if (predicate is None or str(row["predicate"]) == predicate)
            and str(row["source_id"]) not in set(excluded)
        ]
        observed = observed[:_MAX_INCLUDED]
        included, unknown = classify_snapshot(observed, as_of=as_of, time_mode=time_mode)
        snapshot_id = new_id("snap")
        repo.insert_snapshot(
            graph,
            {
                "id": snapshot_id,
                "as_of_time": as_of,
                "time_mode": time_mode,
                "policy_version": self.settings.policy_version,
                "predicate": predicate or "",
                "exclude_source_ids": json.dumps(excluded),
                "validity_unknown_ids": json.dumps(unknown),
                "idempotency_key": idempotency_key,
                "created_at": to_iso(datetime.now(UTC)),
                "entity_ids": entities,
            },
            [
                {
                    "assertion_id": member.assertion_id,
                    "status": member.status,
                    "reason": member.reason,
                    "supersedes_ids": json.dumps(list(member.supersedes_ids)),
                    "conflicts_with_ids": json.dumps(list(member.conflicts_with_ids)),
                }
                for member in included
            ],
        )
        log_event("memory.snapshot_written", assertion_id=snapshot_id)
        return self._snapshot_result(graph, snapshot_id), True

    def get_snapshot(self, tenant_id: str, snapshot_id: str) -> SnapshotResult:
        graph = self.store.graph_for_tenant(tenant_id)
        return self._snapshot_result(graph, snapshot_id)

    def evidence(self, tenant_id: str, assertion_id: str) -> EvidencePath:
        row = repo.evidence_path(self.store.graph_for_tenant(tenant_id), assertion_id)
        if row is None:
            raise FaultlineError("not_found", "Assertion not found", 404)
        return EvidencePath(
            assertion_id=str(row["assertion_id"]),
            source_id=_optional(row.get("source_id")),
            event_id=_optional(row.get("event_id")),
            session_id=_optional(row.get("session_id")),
            entity_id=str(row["entity_id"]),
            status=str(row["status"]),
            supersedes_ids=list(row["supersedes_ids"]),
            conflicts_with_ids=list(row["conflicts_with_ids"]),
        )

    def create_replay(
        self,
        tenant_id: str,
        *,
        question: str,
        predicate: str,
        snapshot_id: str,
        idempotency_key: str,
    ) -> tuple[ReplayResult, bool]:
        if predicate not in PREDICATES:
            raise FaultlineError("validation_error", "Predicate is not allow-listed", 400)
        graph = self.store.graph_for_tenant(tenant_id)
        existing = repo.find_replay_id_by_idempotency(graph, idempotency_key)
        if existing:
            return self._replay_result(graph, existing), False
        snapshot = self._loaded(graph, snapshot_id)
        drafted = self.answerer.answer(question.strip(), predicate, snapshot.members)
        allowed = {member.assertion_id for member in snapshot.members}
        claims, rejected = validate_claims(drafted, allowed)
        replay_id = new_id("replay")
        evidence_ids = [evidence_id for claim in claims for evidence_id in claim.evidence_ids]
        repo.insert_replay(
            graph,
            {
                "id": replay_id,
                "question": question.strip(),
                "predicate": predicate,
                "policy_version": self.settings.policy_version,
                "prompt_version": PROMPT_VERSION,
                "model_version": self.answerer.model_version,
                "idempotency_key": idempotency_key,
                "created_at": to_iso(datetime.now(UTC)),
                "citation_rejected": "true" if rejected else "false",
                "snapshot_id": snapshot_id,
                "evidence_ids": evidence_ids,
            },
            [
                {
                    "claim_id": new_id("claim"),
                    "predicate": claim.predicate or predicate,
                    "value": claim.value or "",
                    "status": claim.status,
                    "evidence_ids": json.dumps(list(claim.evidence_ids)),
                    "evidence_id_list": list(claim.evidence_ids),
                    "wording": claim.wording,
                }
                for claim in claims
            ],
        )
        log_event("memory.replay_written", assertion_id=replay_id)
        return self._replay_result(graph, replay_id), True

    def diff_replays(
        self,
        tenant_id: str,
        candidate_replay_id: str,
        baseline_replay_id: str,
    ) -> ReplayDiff:
        graph = self.store.graph_for_tenant(tenant_id)
        candidate = self._replay_bundle(graph, candidate_replay_id)
        baseline = self._replay_bundle(graph, baseline_replay_id)
        compared = evidence_diff(
            _for_predicate(baseline.members, _claim_predicate(baseline.result)),
            _for_predicate(candidate.members, _claim_predicate(candidate.result)),
            baseline.drafts,
            candidate.drafts,
        )
        return ReplayDiff(
            baseline_replay_id=baseline_replay_id,
            candidate_replay_id=candidate_replay_id,
            added=list(compared["added"]),  # type: ignore[arg-type]
            removed=list(compared["removed"]),  # type: ignore[arg-type]
            unchanged=list(compared["unchanged"]),  # type: ignore[arg-type]
            status_changed=[StatusChange(**item) for item in compared["status_changed"]],  # type: ignore[arg-type]
            added_source_ids=list(compared["added_source_ids"]),  # type: ignore[arg-type]
            removed_source_ids=list(compared["removed_source_ids"]),  # type: ignore[arg-type]
            answer_change=str(compared["answer_change"]),
            explanation=str(compared["explanation"]),
        )

    def _snapshot_result(self, graph, snapshot_id: str) -> SnapshotResult:
        loaded = self._loaded(graph, snapshot_id)
        return loaded.result

    def _loaded(self, graph, snapshot_id: str) -> _LoadedSnapshot:
        raw = repo.load_snapshot(graph, snapshot_id)
        if raw is None:
            raise FaultlineError("not_found", "Snapshot not found", 404)
        rows = raw["rows"]
        head = rows[0]
        members: list[SnapshotMember] = []
        for row in rows:
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
        members.sort(key=lambda item: (item.observed_at, item.assertion_id))
        result = SnapshotResult(
            snapshot_id=str(head["snapshot_id"]),
            as_of_time=str(head["as_of_time"]),
            time_mode=str(head["time_mode"]),
            policy_version=str(head["policy_version"]),
            included=[_member_out(member) for member in members],
            validity_unknown_ids=_json_list(head.get("validity_unknown_ids")),
        )
        return _LoadedSnapshot(result=result, members=members)

    def _replay_result(self, graph, replay_id: str) -> ReplayResult:
        return self._replay_bundle(graph, replay_id).result

    def _replay_bundle(self, graph, replay_id: str) -> _LoadedReplay:
        raw = repo.load_replay(graph, replay_id)
        if raw is None:
            raise FaultlineError("not_found", "Replay not found", 404)
        rows = raw["rows"]
        head = rows[0]
        claims: list[ClaimOut] = []
        drafts: list[AnswerClaimDraft] = []
        for row in rows:
            if not row.get("claim_id"):
                continue
            evidence = _json_list(row.get("evidence_ids"))
            value = _optional(row.get("value"))
            claim = ClaimOut(
                claim_id=str(row["claim_id"]),
                predicate=str(row["claim_predicate"]),
                value=value,
                status=str(row["status"]),
                evidence_ids=evidence,
                wording=str(row.get("wording") or ""),
            )
            claims.append(claim)
            drafts.append(
                AnswerClaimDraft(
                    predicate=claim.predicate,
                    value=claim.value,
                    status=claim.status,
                    evidence_ids=tuple(evidence),
                    wording=claim.wording,
                )
            )
        result = ReplayResult(
            replay_id=str(head["replay_id"]),
            snapshot_id=str(head["snapshot_id"]),
            claims=claims,
            model_version=str(head["model_version"]),
            prompt_version=str(head["prompt_version"]),
            citation_rejected=_flag(head.get("citation_rejected")),
        )
        snapshot = self._loaded(graph, result.snapshot_id)
        return _LoadedReplay(result=result, drafts=drafts, members=snapshot.members)


class _LoadedSnapshot:
    def __init__(self, result: SnapshotResult, members: list[SnapshotMember]) -> None:
        self.result = result
        self.members = members


class _LoadedReplay:
    def __init__(
        self,
        result: ReplayResult,
        drafts: list[AnswerClaimDraft],
        members: list[SnapshotMember],
    ) -> None:
        self.result = result
        self.drafts = drafts
        self.members = members


def _claim_predicate(result: ReplayResult) -> str:
    if not result.claims:
        return ""
    return result.claims[0].predicate


def _for_predicate(members: list[SnapshotMember], predicate: str) -> list[SnapshotMember]:
    if not predicate:
        return members
    return [member for member in members if member.predicate == predicate]


def _observed(row: dict) -> ObservedAssertion:
    return ObservedAssertion(
        assertion_id=str(row["assertion_id"]),
        predicate=str(row["predicate"]),
        value=str(row["value"]),
        observed_at=str(row["observed_at"]),
        valid_from=_optional(row.get("valid_from")),
        valid_to=_optional(row.get("valid_to")),
        confidence=float(row["confidence"] or 0),
        source_id=str(row["source_id"]),
        event_id=_optional(row.get("event_id")),
        trust_tier=str(row["trust_tier"]),
        supersedes_ids=tuple(row["supersedes_ids"]),
        superseded_by_ids=tuple(row["superseded_by_ids"]),
        conflict_ids=tuple(row["conflict_ids"]),
    )


def _member_out(member: SnapshotMember) -> SnapshotMemberOut:
    return SnapshotMemberOut(
        assertion_id=member.assertion_id,
        predicate=member.predicate,
        value=member.value,
        status=member.status,
        observed_at=member.observed_at,
        valid_from=member.valid_from,
        valid_to=member.valid_to,
        confidence=member.confidence,
        source_id=member.source_id or None,
        event_id=member.event_id,
        supersedes_ids=list(member.supersedes_ids),
        conflicts_with_ids=list(member.conflicts_with_ids),
        reason=member.reason,
    )


def _json_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    text = str(value)
    if not text or text == "None":
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


def _flag(value: object) -> bool:
    return value is True or value == 1 or value == "true"


def _unique(values: list[str]) -> list[str]:
    seen: list[str] = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return seen
