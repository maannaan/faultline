"""Scripted extractor used when no model key is configured and in tests.

A line is recognized when it contains:
`entity=Project Atlas; type=Project; predicate=deploy_region; value=region-c; confidence=0.9`
Optional `; correction_of=assert-region-a`.
"""

from __future__ import annotations

import re

from faultline.schemas.models import ProposedAssertion

_LINE = re.compile(
    r"entity=(?P<entity>[^;]+);\s*type=(?P<etype>[^;]+);\s*"
    r"predicate=(?P<predicate>[^;]+);\s*value=(?P<value>[^;]+);\s*"
    r"confidence=(?P<confidence>[^;\n]+)"
    r"(?:;\s*correction_of=(?P<correction>[^;\n]+))?",
    re.IGNORECASE,
)


class FakeExtractor:
    def extract(self, text: str) -> list[ProposedAssertion]:
        proposals: list[ProposedAssertion] = []
        for match in _LINE.finditer(text):
            correction = match.group("correction")
            proposals.append(
                ProposedAssertion(
                    entity_name=match.group("entity").strip(),
                    entity_type=match.group("etype").strip(),
                    predicate=match.group("predicate").strip(),
                    value=match.group("value").strip(),
                    valid_from=None,
                    valid_to=None,
                    confidence=float(match.group("confidence").strip()),
                    correction_of=correction.strip() if correction else None,
                )
            )
        return proposals
