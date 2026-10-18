"""Claims chosen only from assertions included in a snapshot."""

from __future__ import annotations

from dataclasses import dataclass

from faultline.constants import STATUS_CURRENT, STATUS_DISPUTED
from faultline.memory.temporal import SnapshotMember

PROMPT_VERSION = "answer-template-v1"
MODEL_DETERMINISTIC = "deterministic"

CLAIM_SUPPORTED = "supported"
CLAIM_DISPUTED = "disputed"
CLAIM_INSUFFICIENT = "insufficient"


@dataclass(frozen=True)
class AnswerClaimDraft:
    predicate: str
    value: str | None
    status: str
    evidence_ids: tuple[str, ...]
    wording: str


class DeterministicAnswerer:
    """Selects a claim from snapshot status. No model is involved."""

    model_version = MODEL_DETERMINISTIC

    def answer(
        self,
        question: str,
        predicate: str,
        members: list[SnapshotMember],
    ) -> list[AnswerClaimDraft]:
        del question
        return [select_claim(predicate, members)]


def select_claim(predicate: str, members: list[SnapshotMember]) -> AnswerClaimDraft:
    relevant = [member for member in members if member.predicate == predicate]
    current = [member for member in relevant if member.status == STATUS_CURRENT]
    disputed = [member for member in relevant if member.status == STATUS_DISPUTED]
    if disputed:
        evidence = tuple(member.assertion_id for member in disputed)
        return AnswerClaimDraft(
            predicate=predicate,
            value=None,
            status=CLAIM_DISPUTED,
            evidence_ids=evidence,
            wording="The evidence is disputed, so no value is chosen.",
        )
    if len(current) == 1 or (current and len({member.value for member in current}) == 1):
        evidence = tuple(member.assertion_id for member in current)
        value = current[0].value
        return AnswerClaimDraft(
            predicate=predicate,
            value=value,
            status=CLAIM_SUPPORTED,
            evidence_ids=evidence,
            wording=f"{predicate} is {value}.",
        )
    return AnswerClaimDraft(
        predicate=predicate,
        value=None,
        status=CLAIM_INSUFFICIENT,
        evidence_ids=(),
        wording="The snapshot does not contain an accepted claim.",
    )


def validate_claims(
    claims: list[AnswerClaimDraft],
    allowed_ids: set[str],
) -> tuple[list[AnswerClaimDraft], bool]:
    """Drop any claim that cites an assertion outside the snapshot."""
    validated: list[AnswerClaimDraft] = []
    rejected = False
    for claim in claims:
        if any(evidence_id not in allowed_ids for evidence_id in claim.evidence_ids):
            rejected = True
            validated.append(
                AnswerClaimDraft(
                    predicate=claim.predicate,
                    value=None,
                    status=CLAIM_INSUFFICIENT,
                    evidence_ids=(),
                    wording="A cited assertion is outside the snapshot.",
                )
            )
            continue
        validated.append(claim)
    if not validated:
        validated.append(
            AnswerClaimDraft(
                predicate="",
                value=None,
                status=CLAIM_INSUFFICIENT,
                evidence_ids=(),
                wording="The snapshot does not contain an accepted claim.",
            )
        )
    return validated, rejected
