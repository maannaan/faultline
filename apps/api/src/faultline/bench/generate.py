"""Seeded memory scenarios with ground truth taken from the story, not from the policy.

Each timeline is one entity and one predicate. The generator writes it through
MemoryService, the same write path the API uses, into a separate bench tenant.
Expected answers are stated per scenario below, so a policy bug shows up as a
wrong answer instead of moving the target.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from faultline.constants import PREDICATE_DEPLOY_REGION, PREDICATE_ONCALL_OWNER
from faultline.graph.client import GraphStore
from faultline.memory.ids import to_iso
from faultline.memory.service import MemoryService

BENCH_TENANT = "tenant-bench"
BENCH_USER = "user-bench"
BENCH_AGENT = "agent-bench"
BENCH_SESSION = "session-bench"
BASE_TIME = datetime(2026, 11, 2, 0, 0, tzinfo=UTC)

SUPPORTED = "supported"
DISPUTED = "disputed"
INSUFFICIENT = "insufficient"

SCENARIOS = ("stable", "correction", "chain", "conflict", "unreviewed_noise")

_REGIONS = [f"region-{name}" for name in ("a", "b", "c", "d", "e", "f", "g", "h")]
_OWNERS = ["Priya", "Jordan", "Mei", "Arjun", "Sofia", "Kofi", "Lena", "Omar"]


@dataclass(frozen=True)
class Note:
    assertion_id: str
    value: str
    trust_tier: str
    observed_at: datetime
    correction_of: str | None = None

    @property
    def source_id(self) -> str:
        return f"src-{self.assertion_id}"


@dataclass(frozen=True)
class Question:
    question_id: str
    entity_id: str
    predicate: str
    scenario: str
    as_of: str
    expected_status: str
    expected_value: str | None


@dataclass
class Timeline:
    entity_id: str
    entity_name: str
    predicate: str
    scenario: str
    notes: list[Note] = field(default_factory=list)
    questions: list[Question] = field(default_factory=list)


def build_timelines(entities: int, seed: int) -> list[Timeline]:
    rng = random.Random(seed)
    timelines: list[Timeline] = []
    for index in range(entities):
        entity_id = f"svc-{index:04d}"
        name = f"Service {index:04d}"
        for predicate in (PREDICATE_DEPLOY_REGION, PREDICATE_ONCALL_OWNER):
            scenario = rng.choice(SCENARIOS)
            timelines.append(_timeline(rng, entity_id, name, predicate, scenario))
    return timelines


def _timeline(rng: random.Random, entity_id: str, name: str, predicate: str, scenario: str):
    pool = _REGIONS if predicate == PREDICATE_DEPLOY_REGION else _OWNERS
    values = rng.sample(pool, 3)
    start = BASE_TIME + timedelta(hours=rng.randint(0, 240))
    times = [start]
    for _ in range(2):
        times.append(times[-1] + timedelta(hours=rng.randint(2, 30)))
    prefix = f"{entity_id}-{'region' if predicate == PREDICATE_DEPLOY_REGION else 'oncall'}"
    line = Timeline(entity_id, name, predicate, scenario)

    def note(i: int, trust: str = "reviewed", corrects: int | None = None) -> Note:
        made = Note(
            assertion_id=f"{prefix}-{i}",
            value=values[i],
            trust_tier=trust,
            observed_at=times[i],
            correction_of=f"{prefix}-{corrects}" if corrects is not None else None,
        )
        line.notes.append(made)
        return made

    # Expected answers, scenario by scenario. "Before" is always one hour before
    # the first note, "between" is halfway between two notes, "after" is one hour
    # after the last note.
    if scenario == "stable":
        first = note(0)
        stages = [(INSUFFICIENT, None), (SUPPORTED, first.value)]
    elif scenario == "correction":
        first, second = note(0), note(1, corrects=0)
        stages = [(INSUFFICIENT, None), (SUPPORTED, first.value), (SUPPORTED, second.value)]
    elif scenario == "chain":
        first, second, third = note(0), note(1, corrects=0), note(2, corrects=1)
        stages = [
            (INSUFFICIENT, None),
            (SUPPORTED, first.value),
            (SUPPORTED, second.value),
            (SUPPORTED, third.value),
        ]
    elif scenario == "conflict":
        # Two reviewed sources disagree and neither corrects the other.
        first, _second = note(0), note(1)
        stages = [(INSUFFICIENT, None), (SUPPORTED, first.value), (DISPUTED, None)]
    else:
        # A newer unreviewed note must not replace a reviewed fact.
        first, _noise = note(0), note(1, trust="unreviewed")
        stages = [(INSUFFICIENT, None), (SUPPORTED, first.value), (SUPPORTED, first.value)]

    cutoffs = _cutoffs([item.observed_at for item in line.notes])
    for stage, ((status, value), cutoff) in enumerate(zip(stages, cutoffs, strict=True)):
        line.questions.append(
            Question(
                question_id=f"{prefix}-q{stage}",
                entity_id=entity_id,
                predicate=predicate,
                scenario=scenario,
                as_of=to_iso(cutoff),
                expected_status=status,
                expected_value=value,
            )
        )
    return line


def _cutoffs(times: list[datetime]) -> list[datetime]:
    points = [times[0] - timedelta(hours=1)]
    for earlier, later in zip(times, times[1:], strict=False):
        points.append(earlier + (later - earlier) / 2)
    points.append(times[-1] + timedelta(hours=1))
    return points


def write_timelines(
    service: MemoryService, timelines: list[Timeline], tenant_id: str = BENCH_TENANT
) -> int:
    """Write every note through the product write path. Returns notes written."""
    service.ensure_user(tenant_id, BENCH_USER)
    service.ensure_agent(tenant_id, BENCH_AGENT, "bench", "0.1")
    service.ensure_session(tenant_id, BENCH_SESSION, BENCH_USER, BASE_TIME)
    written = 0
    for line in timelines:
        service.ensure_entity(
            tenant_id,
            entity_id=line.entity_id,
            canonical_name=line.entity_name,
            entity_type="Service",
        )
        for item in line.notes:
            service.create_source(
                tenant_id,
                source_id=item.source_id,
                source_type="synthetic_doc",
                trust_tier=item.trust_tier,
                observed_at=item.observed_at,
                title=f"{line.entity_name} {line.predicate} note",
                text=f"{line.entity_name} {line.predicate} is {item.value}.",
                session_id=BENCH_SESSION,
                agent_id=BENCH_AGENT,
            )
            service.create_assertion(
                tenant_id,
                entity_id=line.entity_id,
                assertion_id=item.assertion_id,
                predicate=line.predicate,
                value=item.value,
                source_id=item.source_id,
                observed_at=item.observed_at,
                confidence=0.9,
                idempotency_key=f"bench:{item.assertion_id}",
                correction_of=item.correction_of,
                session_id=BENCH_SESSION,
                agent_id=BENCH_AGENT,
            )
            written += 1
    return written


def reset_bench_graph(store: GraphStore, tenant_id: str = BENCH_TENANT) -> None:
    store.delete_tenant_graph(tenant_id)
