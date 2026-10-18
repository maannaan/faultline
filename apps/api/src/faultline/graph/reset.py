"""Delete only the two known development tenant graphs."""

from __future__ import annotations

import sys

from faultline.config import get_settings
from faultline.constants import KNOWN_TENANTS
from faultline.graph.client import GraphStore


def reset_known_tenants(store: GraphStore | None = None, settings=None) -> None:
    settings = settings or get_settings()
    if settings.app_env != "development":
        raise SystemExit("Reset is only available when APP_ENV=development")
    store = store or GraphStore(settings)
    for tenant_id in KNOWN_TENANTS:
        store.delete_tenant_graph(tenant_id)


def main() -> None:
    try:
        reset_known_tenants()
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
