"""Write throughput, as-of read latency and bisect probe counts on growing bench graphs."""

from __future__ import annotations

import random
import statistics
import time
from datetime import timedelta
from typing import Any

from faultline.bench.generate import (
    BASE_TIME,
    BENCH_AGENT,
    BENCH_SESSION,
    BENCH_TENANT,
    build_timelines,
    reset_bench_graph,
    write_timelines,
)
from faultline.constants import PREDICATE_DEPLOY_REGION
from faultline.graph import repository as repo
from faultline.graph.client import GraphStore
from faultline.graph.subgraph import _observed
from faultline.memory.ids import to_iso
from faultline.memory.service import MemoryService
from faultline.memory.temporal import classify_snapshot
from faultline.replay.answer import select_claim
from faultline.replay.bisect import answer_at, run_bisect

READ_SAMPLE = 200


def run_scale(service: MemoryService, store: GraphStore, sizes: list[int], seed: int) -> list[dict]:
    results = []
    for entities in sizes:
        reset_bench_graph(store)
        timelines = build_timelines(entities, seed)
        started = time.perf_counter()
        notes = write_timelines(service, timelines)
        write_s = time.perf_counter() - started
        graph = store.graph_for_tenant(BENCH_TENANT)
        questions = [q for line in timelines for q in line.questions]
        sample = random.Random(seed).sample(questions, min(READ_SAMPLE, len(questions)))
        scoped = _time(
            lambda q: answer_at(graph, entity_id=q.entity_id, predicate=q.predicate, as_of=q.as_of),
            sample,
        )
        full = _time(lambda q: _full_scan_answer(graph, q.entity_id, q.predicate, q.as_of), sample)
        results.append(
            {
                "entities": entities,
                "notes_written": notes,
                "graph": repo.graph_size(graph),
                "write_seconds": round(write_s, 2),
                "writes_per_second": round(notes / write_s, 1) if write_s else 0.0,
                "read_sample": len(sample),
                "as_of_read_ms": scoped,
                "full_scan_read_ms": full,
            }
        )
    return results


def run_bisect_efficiency(
    service: MemoryService, store: GraphStore, lengths: list[int], seed: int
) -> list[dict]:
    """One long history per length: a reviewed fact, then N unreviewed notes, and one
    reviewed correction hidden at a random position. Bisect must name that correction."""
    reset_bench_graph(store)
    rng = random.Random(seed)
    service.ensure_user(BENCH_TENANT, "user-bench")
    service.ensure_agent(BENCH_TENANT, BENCH_AGENT, "bench", "0.1")
    service.ensure_session(BENCH_TENANT, BENCH_SESSION, "user-bench", BASE_TIME)
    graph = store.graph_for_tenant(BENCH_TENANT)
    results = []
    for length in lengths:
        entity_id = f"hist-{length:04d}"
        service.ensure_entity(
            BENCH_TENANT,
            entity_id=entity_id,
            canonical_name=f"History {length}",
            entity_type="Service",
        )
        flip_at = rng.randint(0, length - 1)
        times = [BASE_TIME + timedelta(minutes=10 * i) for i in range(length + 1)]
        _note(service, entity_id, f"{entity_id}-base", "region-base", "reviewed", times[0])
        culprit = ""
        for i in range(length):
            aid = f"{entity_id}-n{i}"
            if i == flip_at:
                culprit = aid
                _note(
                    service,
                    entity_id,
                    aid,
                    "region-new",
                    "reviewed",
                    times[i + 1],
                    correction_of=f"{entity_id}-base",
                )
            else:
                _note(service, entity_id, aid, f"noise-{i}", "unreviewed", times[i + 1])
        result = run_bisect(
            graph,
            entity_id=entity_id,
            predicate=PREDICATE_DEPLOY_REGION,
            good_as_of=times[0] + timedelta(minutes=1),
            bad_as_of=times[-1] + timedelta(minutes=1),
            time_mode="known",
        )
        results.append(
            {
                "history_length": length,
                "candidates": result.candidates,
                "bisect_probes": len(result.probes),
                "linear_probes": flip_at + 1,
                "linear_worst_case": result.candidates,
                "found_culprit": result.culprit_assertion_ids == [culprit],
                "first_bad_as_of": result.first_bad_as_of,
            }
        )
    return results


def _note(service, entity_id, aid, value, trust, observed_at, correction_of=None) -> None:
    service.create_source(
        BENCH_TENANT,
        source_id=f"src-{aid}",
        source_type="synthetic_doc",
        trust_tier=trust,
        observed_at=observed_at,
        title=f"{entity_id} note",
        text=f"{entity_id} region {value}",
        session_id=BENCH_SESSION,
        agent_id=BENCH_AGENT,
    )
    service.create_assertion(
        BENCH_TENANT,
        entity_id=entity_id,
        assertion_id=aid,
        predicate=PREDICATE_DEPLOY_REGION,
        value=value,
        source_id=f"src-{aid}",
        observed_at=observed_at,
        confidence=0.9,
        idempotency_key=f"bench:{aid}",
        correction_of=correction_of,
        session_id=BENCH_SESSION,
        agent_id=BENCH_AGENT,
    )


def _full_scan_answer(graph: Any, entity_id: str, predicate: str, as_of: str):
    """The read path before entity scoping: fetch every entity, filter in Python."""
    rows = [
        _observed(row)
        for row in repo.observed_assertions(graph, as_of)
        if str(row["entity_id"]) == entity_id
    ]
    members, _ = classify_snapshot(rows, as_of=as_of, time_mode="known")
    return select_claim(predicate, members)


def _time(fn, sample) -> dict[str, float]:
    timings = []
    for question in sample:
        started = time.perf_counter()
        fn(question)
        timings.append((time.perf_counter() - started) * 1000)
    ordered = sorted(timings)
    return {
        "p50": round(statistics.median(ordered), 2),
        "p95": round(ordered[max(0, round(0.95 * len(ordered)) - 1)], 2),
    }


__all__ = ["run_bisect_efficiency", "run_scale", "to_iso"]
