"""Memory bisect: find the first recorded moment an answer took its later value.

Each probe is an as-of read of the FalkorDB graph, classified with the same
rules snapshots use and answered by the deterministic claim selector. Nothing
is written. Like git bisect, it assumes the answer flips once in the range.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from faultline.constants import PREDICATES
from faultline.errors import FaultlineError
from faultline.graph import repository as repo
from faultline.graph.subgraph import _observed
from faultline.memory.ids import to_iso
from faultline.memory.temporal import SnapshotMember, classify_snapshot
from faultline.replay.answer import AnswerClaimDraft, select_claim
from faultline.replay.diff import evidence_diff
from faultline.schemas.models import BisectProbe, BisectResult


def run_bisect(
    graph: Any,
    *,
    entity_id: str,
    predicate: str,
    good_as_of: datetime,
    bad_as_of: datetime,
    time_mode: str,
) -> BisectResult:
    if predicate not in PREDICATES:
        raise FaultlineError("validation_error", "Predicate is not allow-listed", 400)
    if not repo.entity_exists(graph, entity_id):
        raise FaultlineError("not_found", "Entity not found", 404)
    good_at, bad_at = to_iso(good_as_of), to_iso(bad_as_of)
    if good_at >= bad_at:
        raise FaultlineError("validation_error", "good_as_of must be before bad_as_of", 400)

    def probe(cutoff: str) -> tuple[list[SnapshotMember], AnswerClaimDraft]:
        rows = [
            _observed(row)
            for row in repo.observed_assertions(graph, cutoff)
            if str(row["entity_id"]) == entity_id
        ]
        members, _ = classify_snapshot(rows, as_of=cutoff, time_mode=time_mode)
        return members, select_claim(predicate, members)

    good_members, good_claim = probe(good_at)
    bad_members, bad_claim = probe(bad_at)
    bad_key = _key(bad_claim)
    good = _probe_out(good_at, good_claim, "good")
    bad = _probe_out(bad_at, bad_claim, "bad")

    candidates = sorted(
        {
            str(row["observed_at"])
            for row in repo.observed_assertions(graph, bad_at)
            if str(row["entity_id"]) == entity_id
            and str(row["predicate"]) == predicate
            and good_at < str(row["observed_at"]) <= bad_at
        }
    )
    if _key(good_claim) == bad_key or not candidates:
        return BisectResult(
            entity_id=entity_id,
            predicate=predicate,
            good=good,
            bad=bad,
            flipped=False,
            candidates=len(candidates),
            probes=[],
            culprit_assertion_ids=[],
            culprit_source_ids=[],
            culprit_event_ids=[],
            explanation="The answer is the same at both cutoffs. No flip in range.",
        )

    probes: list[BisectProbe] = []
    cache: dict[str, tuple[list[SnapshotMember], AnswerClaimDraft]] = {}

    def check(index: int) -> bool:
        cutoff = candidates[index]
        cache[cutoff] = probe(cutoff)
        is_bad = _key(cache[cutoff][1]) == bad_key
        probes.append(_probe_out(cutoff, cache[cutoff][1], "bad" if is_bad else "good"))
        return is_bad

    # The last candidate answers like bad_as_of: nothing on this predicate is observed after it.
    low, high = -1, len(candidates) - 1
    while high - low > 1:
        middle = (low + high) // 2
        if check(middle):
            high = middle
        else:
            low = middle
    if not probes:
        check(high)

    first_bad = candidates[high]
    after_members, after_claim = cache.get(first_bad) or probe(first_bad)
    if high > 0:
        before_cutoff = candidates[high - 1]
        before_members, before_claim = cache.get(before_cutoff) or probe(before_cutoff)
    else:
        before_members, before_claim = good_members, good_claim
    culprits = [
        member
        for member in after_members
        if member.predicate == predicate and member.observed_at == first_bad
    ]
    compared = evidence_diff(
        [member for member in before_members if member.predicate == predicate],
        [member for member in after_members if member.predicate == predicate],
        [before_claim],
        [after_claim],
    )
    return BisectResult(
        entity_id=entity_id,
        predicate=predicate,
        good=good,
        bad=bad,
        flipped=True,
        candidates=len(candidates),
        probes=probes,
        first_bad_as_of=first_bad,
        culprit_assertion_ids=[member.assertion_id for member in culprits],
        culprit_source_ids=sorted({member.source_id for member in culprits if member.source_id}),
        culprit_event_ids=sorted({member.event_id for member in culprits if member.event_id}),
        explanation=str(compared["explanation"]),
    )


def _key(claim: AnswerClaimDraft) -> tuple[str, str | None]:
    return claim.status, claim.value


def _probe_out(cutoff: str, claim: AnswerClaimDraft, verdict: str) -> BisectProbe:
    return BisectProbe(
        as_of=cutoff,
        status=claim.status,
        value=claim.value,
        evidence_ids=list(claim.evidence_ids),
        verdict=verdict,  # type: ignore[arg-type]
    )
