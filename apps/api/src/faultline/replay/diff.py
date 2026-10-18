"""Deterministic evidence diff. The model does not write this text."""

from __future__ import annotations

from faultline.memory.temporal import SnapshotMember
from faultline.replay.answer import AnswerClaimDraft

ANSWER_EVIDENCE_CHANGED = "evidence_changed"
ANSWER_WORDING_ONLY = "wording_only"


def evidence_diff(
    baseline_rows: list[SnapshotMember],
    candidate_rows: list[SnapshotMember],
    baseline_claims: list[AnswerClaimDraft],
    candidate_claims: list[AnswerClaimDraft],
) -> dict[str, object]:
    baseline = {row.assertion_id: row for row in baseline_rows}
    candidate = {row.assertion_id: row for row in candidate_rows}
    added = sorted(set(candidate) - set(baseline))
    removed = sorted(set(baseline) - set(candidate))
    unchanged = sorted(
        assertion_id
        for assertion_id in set(baseline) & set(candidate)
        if baseline[assertion_id].status == candidate[assertion_id].status
    )
    status_changed = [
        {
            "assertion_id": assertion_id,
            "from_status": baseline[assertion_id].status,
            "to_status": candidate[assertion_id].status,
        }
        for assertion_id in sorted(set(baseline) & set(candidate))
        if baseline[assertion_id].status != candidate[assertion_id].status
    ]
    baseline_sources = {row.source_id for row in baseline_rows if row.source_id}
    candidate_sources = {row.source_id for row in candidate_rows if row.source_id}
    memory_changed = bool(added or removed or status_changed)
    wording_differs = _wording(baseline_claims) != _wording(candidate_claims)
    if memory_changed:
        answer_change = ANSWER_EVIDENCE_CHANGED
    elif wording_differs:
        answer_change = ANSWER_WORDING_ONLY
    else:
        answer_change = ANSWER_WORDING_ONLY
    return {
        "added": added,
        "removed": removed,
        "unchanged": unchanged,
        "status_changed": status_changed,
        "added_source_ids": sorted(candidate_sources - baseline_sources),
        "removed_source_ids": sorted(baseline_sources - candidate_sources),
        "answer_change": answer_change,
        "explanation": _explanation(candidate, added, status_changed, memory_changed),
    }


def _wording(claims: list[AnswerClaimDraft]) -> tuple[str, ...]:
    return tuple(claim.wording for claim in claims)


def _explanation(
    candidate: dict[str, SnapshotMember],
    added: list[str],
    status_changed: list[dict[str, str]],
    memory_changed: bool,
) -> str:
    if not memory_changed:
        return "Evidence and status match. A wording difference is not a memory change."
    changed_ids = {item["assertion_id"] for item in status_changed}
    sentences: list[str] = []
    for assertion_id in added:
        member = candidate[assertion_id]
        for older_id in member.supersedes_ids:
            if older_id in changed_ids:
                sentences.append(
                    f"{assertion_id} SUPERSEDES {older_id}, "
                    "so the earlier claim is superseded at the later cutoff."
                )
        for other_id in member.conflicts_with_ids:
            if member.status == "disputed":
                pair = " CONFLICTS_WITH ".join(sorted((assertion_id, other_id)))
                sentence = f"{pair}, so neither value is chosen."
                if sentence not in sentences:
                    sentences.append(sentence)
    if not sentences:
        sentences.append("The evidence set changed between the two snapshots.")
    return " ".join(sentences)
