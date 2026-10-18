"""Deterministic memory policy. The model never sets assertion status."""

from __future__ import annotations

from dataclasses import dataclass

from faultline.constants import (
    RESOLUTION_ACCEPTED,
    RESOLUTION_CONFLICT,
    RESOLUTION_SUPERSEDES,
    RESOLUTION_UNREVIEWED,
    STATUS_CURRENT,
    STATUS_DISPUTED,
    STATUS_UNVERIFIED,
    TRUST_REVIEWED,
)


@dataclass(frozen=True)
class PolicyDecision:
    status: str
    resolution: str
    resolution_reason: str
    supersede_id: str | None
    dispute_ids: tuple[str, ...]


def decide_assertion(
    *,
    trust_tier: str,
    correction_of: str | None,
    conflicting_ids: list[str],
) -> PolicyDecision:
    if trust_tier != TRUST_REVIEWED:
        return PolicyDecision(
            status=STATUS_UNVERIFIED,
            resolution=RESOLUTION_UNREVIEWED,
            resolution_reason="Source is not reviewed, so the claim stays unverified.",
            supersede_id=None,
            dispute_ids=(),
        )
    if correction_of:
        return PolicyDecision(
            status=STATUS_CURRENT,
            resolution=RESOLUTION_SUPERSEDES,
            resolution_reason="Reviewed correction superseded the prior assertion.",
            supersede_id=correction_of,
            dispute_ids=(),
        )
    if conflicting_ids:
        return PolicyDecision(
            status=STATUS_DISPUTED,
            resolution=RESOLUTION_CONFLICT,
            resolution_reason="Two reviewed sources disagree without an explicit correction.",
            supersede_id=None,
            dispute_ids=tuple(conflicting_ids),
        )
    return PolicyDecision(
        status=STATUS_CURRENT,
        resolution=RESOLUTION_ACCEPTED,
        resolution_reason="Reviewed source accepted as the current claim.",
        supersede_id=None,
        dispute_ids=(),
    )
