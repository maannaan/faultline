"""Memory regression tests: expected answers at cutoffs, checked against the graph.

`python -m faultline.bench.memory_tests` seeds Project Atlas if needed, runs every
case in memory-tests.yaml and exits non-zero on a failure. In CI it also writes a
table to the job summary.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from faultline.config import get_settings
from faultline.graph.client import GraphStore
from faultline.graph.seed import TENANT_ID, seed_atlas
from faultline.memory.ids import to_iso
from faultline.replay.bisect import answer_at
from faultline.schemas.models import MemoryTestCase, MemoryTestReport

CASES_PATH = Path(__file__).resolve().parents[3] / "memory-tests.yaml"


def load_cases(path: Path = CASES_PATH) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def run_cases(graph: Any, spec: dict[str, Any]) -> MemoryTestReport:
    entity_id = str(spec["entity"])
    results: list[MemoryTestCase] = []
    for case in spec["cases"]:
        expect = case["expect"]
        _, claim = answer_at(
            graph,
            entity_id=entity_id,
            predicate=str(case["predicate"]),
            as_of=_iso(str(case["as_of"])),
            time_mode=str(case.get("time_mode", "known")),
            exclude_source_ids=frozenset(case.get("exclude_source_ids", [])),
        )
        problems: list[str] = []
        if claim.status != expect["status"]:
            problems.append(f"status {claim.status} != {expect['status']}")
        if claim.value != expect.get("value"):
            problems.append(f"value {claim.value} != {expect.get('value')}")
        if sorted(claim.evidence_ids) != sorted(expect.get("cites", [])):
            cited, wanted = sorted(claim.evidence_ids), sorted(expect.get("cites", []))
            problems.append(f"cites {cited} != {wanted}")
        results.append(
            MemoryTestCase(
                name=str(case["name"]),
                description=str(case.get("description", "")),
                predicate=str(case["predicate"]),
                as_of=str(case["as_of"]),
                time_mode=str(case.get("time_mode", "known")),
                expected_status=str(expect["status"]),
                expected_value=expect.get("value"),
                actual_status=claim.status,
                actual_value=claim.value,
                cites=list(claim.evidence_ids),
                passed=not problems,
                message="; ".join(problems),
            )
        )
    passed = sum(item.passed for item in results)
    return MemoryTestReport(passed=passed, failed=len(results) - passed, cases=results)


def _iso(value: str) -> str:
    return to_iso(datetime.fromisoformat(value.replace("Z", "+00:00")))


def _markdown(report: MemoryTestReport) -> str:
    lines = [
        f"### Memory regression tests: {report.passed} passed, {report.failed} failed",
        "",
        "| | Case | Cutoff | Expected | Actual |",
        "| --- | --- | --- | --- | --- |",
    ]
    for case in report.cases:
        mark = "✅" if case.passed else "❌"
        expected = f"{case.expected_status} {case.expected_value or ''}".strip()
        actual = f"{case.actual_status} {case.actual_value or ''}".strip()
        cutoff = f"{case.as_of} {case.time_mode}"
        lines.append(f"| {mark} | `{case.name}` | {cutoff} | {expected} | {actual} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    settings = get_settings()
    store = GraphStore(settings)
    seed_atlas(settings, store)
    report = run_cases(store.graph_for_tenant(TENANT_ID), load_cases())
    summary = _markdown(report)
    print(summary)
    for case in report.cases:
        if not case.passed:
            print(f"FAIL {case.name}: {case.message}", file=sys.stderr)
    target = os.environ.get("GITHUB_STEP_SUMMARY")
    if target:
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(summary)
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
