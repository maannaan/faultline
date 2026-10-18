"""Safe FalkorDB graph names. Callers never interpolate tenant text into Cypher."""

from __future__ import annotations

import re

from faultline.errors import FaultlineError

_GRAPH_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def graph_name_for_tenant(tenant_id: str) -> str:
    slug = tenant_id.strip().replace("-", "_")
    name = f"tenant_{slug}"
    if not _GRAPH_NAME.fullmatch(name):
        raise FaultlineError("validation_error", "Invalid tenant graph name", 400)
    return name
