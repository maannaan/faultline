"""Identifiers and normalized text."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from ulid import ULID

from faultline.errors import FaultlineError


def new_id(prefix: str) -> str:
    return f"{prefix}_{ULID()}"


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_text(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def to_iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise FaultlineError("validation_error", "timestamp must include a timezone", 400)
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
