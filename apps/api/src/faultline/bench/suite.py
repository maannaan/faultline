"""Score memory methods on generated scenarios.

Every method reads the same assertion rows from the bench graph. The baselines
see values, trust tiers and observation times, and ignore the edges. Faultline
uses the as-of query plus SUPERSEDES / CONFLICTS_WITH, exactly as replays do.
"""

from __future__ import annotations

import statistics
import time
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from faultline.bench.generate import (
    BENCH_TENANT,
    DISPUTED,
    INSUFFICIENT,
    SCENARIOS,
    SUPPORTED,
    Question,
    Timeline,
)
from faultline.graph import repository as repo
from faultline.replay.bisect import answer_at

FAR = "9999-01-01T00:00:00Z"

METHODS = {
    "no_memory": "No memory",
    "kv_current": "Key-value store (last write wins, no history)",
    "log_latest": "Append-only log, latest line before the question",
    "log_latest_reviewed": "Append-only log, latest reviewed line",
    "faultline": "Faultline (FalkorDB edges + policy)",
}

Answer = tuple[str, str | None]


def score(graph: Any, timelines: list[Timeline]) -> dict[str, Any]:
    rows = repo.observed_assertions(graph, FAR)
    by_key: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_key[(str(row["entity_id"]), str(row["predicate"]))].append(row)
    for items in by_key.values():
        items.sort(key=lambda row: (str(row["observed_at"]), str(row["assertion_id"])))

    questions = [question for line in timelines for question in line.questions]
    answerers: dict[str, Callable[[Question], Answer]] = {
        "no_memory": lambda q: (INSUFFICIENT, None),
        "kv_current": lambda q: _latest(by_key[(q.entity_id, q.predicate)]),
        "log_latest": lambda q: _latest(_before(by_key[(q.entity_id, q.predicate)], q.as_of)),
        "log_latest_reviewed": lambda q: _latest(
            [
                row
                for row in _before(by_key[(q.entity_id, q.predicate)], q.as_of)
                if row["trust_tier"] == "reviewed"
            ]
        ),
        "faultline": lambda q: _faultline(graph, q),
    }
    methods = []
    for name, answer in answerers.items():
        methods.append(_run(name, answer, questions, by_key))
    return {
        "questions": len(questions),
        "timelines": len(timelines),
        "scenario_counts": _scenario_counts(timelines),
        "methods": methods,
    }


def _before(rows: list[dict[str, Any]], as_of: str) -> list[dict[str, Any]]:
    return [row for row in rows if str(row["observed_at"]) <= as_of]


def _latest(rows: list[dict[str, Any]]) -> Answer:
    if not rows:
        return INSUFFICIENT, None
    return SUPPORTED, str(rows[-1]["value"])


def _faultline(graph: Any, question: Question) -> Answer:
    _members, claim = answer_at(
        graph,
        entity_id=question.entity_id,
        predicate=question.predicate,
        as_of=question.as_of,
    )
    return claim.status, claim.value


def _run(name, answer, questions: list[Question], by_key) -> dict[str, Any]:
    errors: dict[str, int] = defaultdict(int)
    per_scenario: dict[str, list[int]] = {scenario: [0, 0] for scenario in SCENARIOS}
    timings: list[float] = []
    for question in questions:
        started = time.perf_counter()
        status, value = answer(question)
        timings.append((time.perf_counter() - started) * 1000)
        correct = status == question.expected_status and value == question.expected_value
        per_scenario[question.scenario][1] += 1
        if correct:
            per_scenario[question.scenario][0] += 1
        else:
            errors[_error_kind(question, status, value, by_key)] += 1
    correct_total = sum(hit for hit, _ in per_scenario.values())
    return {
        "method": name,
        "label": METHODS[name],
        "correct": correct_total,
        "questions": len(questions),
        "accuracy": round(correct_total / len(questions), 4) if questions else 0.0,
        "by_scenario": {
            scenario: {"correct": hit, "questions": total}
            for scenario, (hit, total) in per_scenario.items()
        },
        "errors": dict(sorted(errors.items())),
        "latency_ms_p50": round(statistics.median(timings), 3) if timings else 0.0,
        "latency_ms_p95": round(_percentile(timings, 95), 3) if timings else 0.0,
    }


def _error_kind(question: Question, status: str, value: str | None, by_key) -> str:
    """Name the failure so the report says how a method was wrong, not only that it was."""
    if question.expected_status == DISPUTED:
        return "missed_conflict" if status == SUPPORTED else "wrong_abstain"
    if status == DISPUTED:
        return "false_conflict"
    if status == INSUFFICIENT:
        return "missed_answer"
    if question.expected_status == INSUFFICIENT:
        return "answered_too_early"
    rows = by_key[(question.entity_id, question.predicate)]
    match = [row for row in rows if str(row["value"]) == value]
    if any(str(row["observed_at"]) > question.as_of for row in match):
        return "future_value"
    if any(row["trust_tier"] != "reviewed" for row in match):
        return "untrusted_value"
    return "stale_value"


def _scenario_counts(timelines: list[Timeline]) -> dict[str, int]:
    counts = {scenario: 0 for scenario in SCENARIOS}
    for line in timelines:
        counts[line.scenario] += 1
    return counts


def _percentile(values: list[float], pct: int) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(pct / 100 * len(ordered)) - 1))
    return ordered[index]


__all__ = ["BENCH_TENANT", "METHODS", "score"]
