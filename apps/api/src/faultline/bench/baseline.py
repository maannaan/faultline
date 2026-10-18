"""Score three deterministic methods on the seeded Atlas questions."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from faultline.config import Settings
from faultline.errors import FaultlineError
from faultline.graph import repository as repo
from faultline.graph.client import GraphStore
from faultline.memory.ids import new_id
from faultline.replay.answer import CLAIM_DISPUTED, CLAIM_INSUFFICIENT, DeterministicAnswerer
from faultline.replay.service import LabService

EARLY = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
LATE = datetime(2026, 10, 16, 13, 0, tzinfo=UTC)
ENTITY_ID = "project-atlas"
TENANT_ID = "tenant-synthetic"
FAR = "9999-01-01T00:00:00Z"
LIMITATIONS = (
    "These scores are three synthetic questions on one seeded project. "
    "They do not show a general advantage over other memory systems."
)

QUESTIONS = (
    {
        "id": "early-region",
        "as_of": EARLY,
        "predicate": "deploy_region",
        "question": "Which deployment region should the rollout use?",
        "expected_status": "supported",
        "expected_value": "region-a",
    },
    {
        "id": "late-region",
        "as_of": LATE,
        "predicate": "deploy_region",
        "question": "Which deployment region should the rollout use?",
        "expected_status": "supported",
        "expected_value": "region-b",
    },
    {
        "id": "late-oncall",
        "as_of": LATE,
        "predicate": "oncall_owner",
        "question": "Who is the on-call owner?",
        "expected_status": CLAIM_DISPUTED,
        "expected_value": None,
    },
)


def run_baseline(settings: Settings, store: GraphStore, tenant_id: str = TENANT_ID) -> dict:
    if settings.app_env != "development":
        raise FaultlineError("validation_error", "Benchmarks run only in development", 400)
    if tenant_id != TENANT_ID:
        raise FaultlineError("not_found", "Benchmark not found", 404)
    graph = store.graph_for_tenant(tenant_id)
    rows = [
        row
        for row in repo.observed_assertions(graph, FAR)
        if str(row["entity_id"]) == ENTITY_ID
    ]
    lab = LabService(settings, store, DeterministicAnswerer())
    methods = [
        _score("no_memory", QUESTIONS, lambda item: _no_memory(item), rows),
        _score("flat_summary", QUESTIONS, lambda item: _flat(item, rows), rows),
        _score("faultline", QUESTIONS, lambda item: _faultline(lab, tenant_id, item), rows),
    ]
    return {
        "sample_size": len(QUESTIONS),
        "graph": repo.graph_size(graph),
        "limitations": LIMITATIONS,
        "methods": methods,
    }


def _score(name, questions, answer, rows) -> dict:
    scored = []
    started = time.perf_counter()
    tokens = 0
    for item in questions:
        result = answer(item)
        tokens += _tokens(result["prompt"])
        scored.append(_judge(item, result, rows))
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    covered = sum(1 for row in scored if row["evidence_covered"])
    return {
        "method": name,
        "correct": sum(1 for row in scored if row["correct"]),
        "questions": len(scored),
        "evidence_coverage": round(covered / len(scored), 2),
        "stale_answers": sum(1 for row in scored if row["stale"]),
        "conflict_detections": sum(1 for row in scored if row["status"] == CLAIM_DISPUTED),
        "estimated_tokens": tokens,
        "token_estimate": "character_count_divided_by_4",
        "latency_ms": elapsed_ms,
        "rows": scored,
    }


def _judge(item, result, rows) -> dict:
    value = result["value"]
    status = result["status"]
    correct = status == item["expected_status"] and value == item["expected_value"]
    evidence = result["evidence_ids"]
    allowed = set(result["allowed_ids"])
    covered = bool(evidence) and all(evidence_id in allowed for evidence_id in evidence)
    return {
        "question_id": item["id"],
        "status": status,
        "value": value,
        "evidence_ids": evidence,
        "correct": correct,
        "stale": _stale(value, item, rows),
        "evidence_covered": covered,
        "estimated_tokens": _tokens(result["prompt"]),
    }


def _stale(value, item, rows) -> bool:
    if not value:
        return False
    as_of = item["as_of"].strftime("%Y-%m-%dT%H:%M:%SZ")
    later = [
        row
        for row in rows
        if row["predicate"] == item["predicate"]
        and row["value"] == value
        and str(row["observed_at"]) > as_of
    ]
    earlier = [
        row
        for row in rows
        if row["predicate"] == item["predicate"]
        and row["value"] == value
        and str(row["observed_at"]) <= as_of
    ]
    return bool(later) and not earlier


def _no_memory(item) -> dict:
    return {
        "status": CLAIM_INSUFFICIENT,
        "value": None,
        "evidence_ids": [],
        "allowed_ids": [],
        "prompt": item["question"],
    }


def _flat(item, rows) -> dict:
    lines = sorted(
        (
            f"{row['observed_at']} {row['predicate']}={row['value']}"
            for row in rows
            if row["predicate"] == item["predicate"]
        ),
        key=str,
    )
    latest = [
        row for row in rows if row["predicate"] == item["predicate"]
    ]
    latest.sort(key=lambda row: (str(row["observed_at"]), str(row["assertion_id"])))
    value = str(latest[-1]["value"]) if latest else None
    return {
        "status": "supported" if value else CLAIM_INSUFFICIENT,
        "value": value,
        "evidence_ids": [],
        "allowed_ids": [],
        "prompt": "\n".join(lines),
    }


def _faultline(lab: LabService, tenant_id: str, item) -> dict:
    stamp = new_id("base")
    snapshot, _created = lab.create_snapshot(
        tenant_id,
        as_of_time=item["as_of"],
        time_mode="known",
        entity_ids=[ENTITY_ID],
        predicate=item["predicate"],
        exclude_source_ids=[],
        idempotency_key=f"baseline-snap:{item['id']}:{stamp}",
    )
    replay, _replay_created = lab.create_replay(
        tenant_id,
        question=item["question"],
        predicate=item["predicate"],
        snapshot_id=snapshot.snapshot_id,
        idempotency_key=f"baseline-replay:{item['id']}:{stamp}",
    )
    claim = replay.claims[0]
    prompt = "\n".join(
        f"{member.assertion_id} {member.predicate}={member.value} {member.status}"
        for member in snapshot.included
    )
    return {
        "status": claim.status,
        "value": claim.value,
        "evidence_ids": list(claim.evidence_ids),
        "allowed_ids": [member.assertion_id for member in snapshot.included],
        "prompt": prompt,
    }


def _tokens(prompt: str) -> int:
    return len(prompt) // 4
