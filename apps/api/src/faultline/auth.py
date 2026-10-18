"""Bearer keys resolve to a tenant. Request bodies never choose the tenant."""

from __future__ import annotations

from typing import Annotated

from fastapi import Header, Request

from faultline.errors import FaultlineError
from faultline.logging import tenant_id_var


def require_tenant(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    if authorization is None or not authorization.startswith("Bearer "):
        raise FaultlineError("unauthorized", "Bearer token is required", 401)
    key = authorization.removeprefix("Bearer ").strip()
    tenant_id = request.app.state.settings.tenant_for_key(key)
    if tenant_id is None:
        raise FaultlineError("unauthorized", "Bearer token is required", 401)
    tenant_id_var.set(tenant_id)
    request.state.tenant_id = tenant_id
    return tenant_id
