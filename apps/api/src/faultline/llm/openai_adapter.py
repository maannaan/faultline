"""OpenAI structured extraction. The prompt cannot assign memory status."""

from __future__ import annotations

from faultline.config import Settings
from faultline.constants import PREDICATES
from faultline.errors import FaultlineError
from faultline.llm.client import kimi_extra_body, openai_client
from faultline.schemas.models import ExtractionPayload, ProposedAssertion

_SYSTEM_PROMPT = f"""You extract factual assertions from a source note for a memory graph.
Only use these predicates: {", ".join(PREDICATES)}.
Do not decide whether a fact is current, superseded, disputed, or unverified.
If the note explicitly corrects an earlier assertion and quotes its id,
set correction_of to that id.
If the note does not state a validity interval, set valid_from and valid_to to null.
Return an empty assertions list when the note states no allow-listed fact.
"""


class OpenAIExtractor:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = openai_client(settings)

    def extract(self, text: str) -> list[ProposedAssertion]:
        extra = kimi_extra_body(self.settings)
        try:
            completion = self._client.chat.completions.parse(
                model=self.settings.openai_model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                response_format=ExtractionPayload,
                **({"extra_body": extra} if extra else {}),
            )
        except Exception as exc:
            raise FaultlineError(
                "extraction_failed",
                "The model could not extract assertions.",
                502,
            ) from exc
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise FaultlineError(
                "extraction_failed",
                "The model could not extract assertions.",
                502,
            )
        return list(parsed.assertions)
