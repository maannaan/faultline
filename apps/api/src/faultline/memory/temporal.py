"""As-of status from edges that are visible at a cutoff.

The assertion node's status property stays the status now. This module does
not write it.
"""

from __future__ import annotations

from dataclasses import dataclass

from faultline.constants import (
    STATUS_CURRENT,
    STATUS_DISPUTED,
    STATUS_SUPERSEDED,
    STATUS_UNVERIFIED,
    TRUST_REVIEWED,
)

TIME_KNOWN = "known"
TIME_VALID = "valid"

_REASON_SUPERSEDED = "Superseded by a reviewed correction visible at the cutoff."
_REASON_DISPUTED = "Two reviewed sources disagree without an explicit correction."
_REASON_UNVERIFIED = "Source is not reviewed, so the claim stays unverified."
_REASON_CURRENT = "Reviewed source is current at this cutoff."


@dataclass(frozen=True)
class ObservedAssertion:
    assertion_id: str
    predicate: str
    value: str
    observed_at: str
    valid_from: str | None
    valid_to: str | None
    confidence: float
    source_id: str
    event_id: str | None
    trust_tier: str
    supersedes_ids: tuple[str, ...]
    superseded_by_ids: tuple[str, ...]
    conflict_ids: tuple[str, ...]


@dataclass(frozen=True)
class SnapshotMember:
    assertion_id: str
    predicate: str
    value: str
    status: str
    observed_at: str
    valid_from: str | None
    valid_to: str | None
    confidence: float
    source_id: str
    event_id: str | None
    supersedes_ids: tuple[str, ...]
    conflicts_with_ids: tuple[str, ...]
    reason: str


def classify_snapshot(
    rows: list[ObservedAssertion],
    *,
    as_of: str,
    time_mode: str,
) -> tuple[list[SnapshotMember], list[str]]:
    """Return included members and assertion ids whose validity interval is unknown."""
    if time_mode == TIME_VALID:
        pool = [row for row in rows if _interval_covers(row, as_of)]
        unknown = [row.assertion_id for row in rows if row not in pool]
    else:
        pool = list(rows)
        unknown = []
    pool_ids = {row.assertion_id for row in pool}
    included = [_member(row, pool_ids) for row in pool]
    included.sort(key=lambda item: (item.observed_at, item.assertion_id))
    return included, unknown


def _interval_covers(row: ObservedAssertion, as_of: str) -> bool:
    if not row.valid_from or row.valid_from > as_of:
        return False
    if row.valid_to and row.valid_to <= as_of:
        return False
    return True


def _member(row: ObservedAssertion, pool_ids: set[str]) -> SnapshotMember:
    visible_supersedes = tuple(
        assertion_id for assertion_id in row.supersedes_ids if assertion_id in pool_ids
    )
    visible_conflicts = tuple(
        assertion_id for assertion_id in row.conflict_ids if assertion_id in pool_ids
    )
    superseded_by = [
        assertion_id for assertion_id in row.superseded_by_ids if assertion_id in pool_ids
    ]
    if row.trust_tier != TRUST_REVIEWED:
        status = STATUS_UNVERIFIED
        reason = _REASON_UNVERIFIED
    elif superseded_by:
        status = STATUS_SUPERSEDED
        reason = _REASON_SUPERSEDED
    elif visible_conflicts:
        status = STATUS_DISPUTED
        reason = _REASON_DISPUTED
    else:
        status = STATUS_CURRENT
        reason = _REASON_CURRENT
    return SnapshotMember(
        assertion_id=row.assertion_id,
        predicate=row.predicate,
        value=row.value,
        status=status,
        observed_at=row.observed_at,
        valid_from=row.valid_from,
        valid_to=row.valid_to,
        confidence=row.confidence,
        source_id=row.source_id,
        event_id=row.event_id,
        supersedes_ids=visible_supersedes,
        conflicts_with_ids=visible_conflicts,
        reason=reason,
    )
