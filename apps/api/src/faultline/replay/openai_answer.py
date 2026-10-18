"""OpenAI phrasing for a claim the server already selected."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from faultline.config import Settings
from faultline.llm.client import kimi_extra_body, openai_client
from faultline.memory.temporal import SnapshotMember
from faultline.replay.answer import AnswerClaimDraft, DeterministicAnswerer

_SYSTEM_PROMPT = """You phrase an answer from the supplied evidence only.
You cannot add facts, change status, or choose a winner when the evidence is disputed.
Return evidence_ids copied from the evidence you were given.
If you cannot stay inside those ids, return an empty evidence_ids list.
"""


class _Phrase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    wording: str = Field(min_length=1)
    evidence_ids: list[str]


class OpenAIAnswerer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.model_version = settings.openai_model
        self._client = openai_client(settings)
        self._deterministic = DeterministicAnswerer()

    def answer(
        self,
        question: str,
        predicate: str,
        members: list[SnapshotMember],
    ) -> list[AnswerClaimDraft]:
        selected = self._deterministic.answer(question, predicate, members)[0]
        allowed = {member.assertion_id for member in members}
        extra = kimi_extra_body(self.settings)
        try:
            completion = self._client.chat.completions.parse(
                model=self.settings.openai_model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": _user_payload(question, selected, members),
                    },
                ],
                response_format=_Phrase,
                **({"extra_body": extra} if extra else {}),
            )
        except Exception:
            return [selected]
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            return [selected]
        cited = tuple(parsed.evidence_ids)
        if any(evidence_id not in allowed for evidence_id in cited):
            return [
                AnswerClaimDraft(
                    predicate=predicate,
                    value=selected.value,
                    status=selected.status,
                    evidence_ids=cited,
                    wording=parsed.wording,
                )
            ]
        if set(cited) != set(selected.evidence_ids):
            return [selected]
        return [
            AnswerClaimDraft(
                predicate=selected.predicate,
                value=selected.value,
                status=selected.status,
                evidence_ids=selected.evidence_ids,
                wording=parsed.wording,
            )
        ]


def _user_payload(
    question: str,
    selected: AnswerClaimDraft,
    members: list[SnapshotMember],
) -> str:
    lines = [
        f"Question: {question}",
        f"Predicate: {selected.predicate}",
        f"Status: {selected.status}",
        f"Value: {selected.value or ''}",
        "Evidence:",
    ]
    for member in members:
        if member.assertion_id in selected.evidence_ids:
            lines.append(f"- {member.assertion_id}: {member.predicate}={member.value}")
    return "\n".join(lines)
