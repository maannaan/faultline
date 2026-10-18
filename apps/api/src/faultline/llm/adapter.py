"""Extractor interface. Status is not a field the model is allowed to return."""

from __future__ import annotations

from typing import Protocol

from faultline.schemas.models import ProposedAssertion


class Extractor(Protocol):
    def extract(self, text: str) -> list[ProposedAssertion]:
        """Return proposed assertions. The server assigns status."""
