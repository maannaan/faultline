"""Turn a note into a source plus policy-checked assertions."""

from __future__ import annotations

from datetime import datetime

from faultline.constants import PREDICATES
from faultline.errors import FaultlineError
from faultline.llm.adapter import Extractor
from faultline.logging import log_event
from faultline.memory.ids import normalize_text, to_iso
from faultline.memory.service import MemoryService
from faultline.schemas.models import AssertionResult, NoteIngestResult, ProposedAssertion


def ingest_note(
    service: MemoryService,
    tenant_id: str,
    *,
    text: str,
    trust_tier: str,
    observed_at: datetime,
    session_id: str,
    agent_id: str,
    extractor: Extractor,
) -> NoteIngestResult:
    service.validate_text(text)
    source, _created = service.create_source(
        tenant_id,
        source_type="note",
        trust_tier=trust_tier,
        observed_at=observed_at,
        title="Ingested note",
        text=text,
        session_id=session_id,
        agent_id=agent_id,
    )
    try:
        proposals = extractor.extract(text)
    except Exception:
        log_event("memory.extraction_failed", source_id=source.source_id)
        return NoteIngestResult(
            source_id=source.source_id,
            event_id=source.event_id,
            extraction_status="failed",
            extraction_error="The model could not extract assertions.",
            warnings=[],
            assertions=[],
        )

    assertions: list[AssertionResult] = []
    warnings: list[str] = []
    for index, proposal in enumerate(proposals):
        warning = _proposal_warning(proposal)
        if warning:
            warnings.append(warning)
            continue
        try:
            valid_from = _parse_optional_time(proposal.valid_from)
            valid_to = _parse_optional_time(proposal.valid_to)
        except (ValueError, FaultlineError):
            warnings.append("Skipped a proposal with an invalid validity interval.")
            continue
        log_event("memory.assertion_proposed", source_id=source.source_id)
        try:
            result, _created_assertion = service.create_assertion(
                tenant_id,
                predicate=proposal.predicate,
                value=proposal.value,
                source_id=source.source_id,
                observed_at=observed_at,
                valid_from=valid_from,
                valid_to=valid_to,
                confidence=proposal.confidence,
                idempotency_key=(
                    f"note:{source.source_id}:{proposal.predicate}:"
                    f"{normalize_text(proposal.value)}"
                ),
                entity_name=proposal.entity_name,
                entity_type=proposal.entity_type,
                correction_of=proposal.correction_of,
                session_id=session_id,
                agent_id=agent_id,
            )
        except FaultlineError as exc:
            warnings.append(exc.message)
            continue
        assertions.append(result)
        if index > 50:
            warnings.append("Stopped after 50 proposals.")
            break
    return NoteIngestResult(
        source_id=source.source_id,
        event_id=source.event_id,
        extraction_status="completed",
        extraction_error=None,
        warnings=warnings,
        assertions=assertions,
    )


def _proposal_warning(proposal: ProposedAssertion) -> str | None:
    if proposal.predicate not in PREDICATES:
        return f"Skipped predicate {proposal.predicate}."
    if not proposal.entity_name.strip() or not proposal.entity_type.strip():
        return "Skipped a proposal with no entity."
    if not proposal.value.strip():
        return "Skipped a proposal with no value."
    if not 0 <= proposal.confidence <= 1:
        return "Skipped a proposal with confidence outside 0 to 1."
    return None


def _parse_optional_time(value: str | None) -> datetime | None:
    if value is None or not str(value).strip():
        return None
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return to_iso_datetime(parsed)


def to_iso_datetime(value: datetime) -> datetime:
    to_iso(value)
    return value
