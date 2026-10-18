"""FalkorDB connection. One graph per tenant, selected on the server."""

from __future__ import annotations

from typing import Any

from falkordb import FalkorDB

from faultline.config import Settings
from faultline.errors import FaultlineError
from faultline.graph.cypher import is_connection_error
from faultline.graph.names import graph_name_for_tenant
from faultline.graph.schema import ensure_schema


class GraphStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._db: FalkorDB | None = None

    def db(self) -> FalkorDB:
        if self._db is None:
            kwargs: dict[str, Any] = {
                "host": self.settings.falkordb_host,
                "port": self.settings.falkordb_port,
                "socket_timeout": 2,
                "socket_connect_timeout": 2,
            }
            if self.settings.falkordb_password:
                kwargs["password"] = self.settings.falkordb_password
            self._db = FalkorDB(**kwargs)
        return self._db

    def ping(self) -> None:
        try:
            self.db().connection.ping()
        except Exception as exc:
            raise FaultlineError("graph_unavailable", "FalkorDB is unavailable", 503) from exc

    def graph_for_tenant(self, tenant_id: str) -> Any:
        name = graph_name_for_tenant(tenant_id)
        try:
            graph = self.db().select_graph(name)
        except Exception as exc:
            if is_connection_error(exc):
                raise FaultlineError("graph_unavailable", "FalkorDB is unavailable", 503) from exc
            raise
        ensure_schema(graph, tenant_id, self.settings.schema_version)
        return graph

    def delete_tenant_graph(self, tenant_id: str) -> None:
        name = graph_name_for_tenant(tenant_id)
        try:
            graph = self.db().select_graph(name)
            graph.delete()
        except Exception as exc:
            if is_connection_error(exc):
                raise FaultlineError("graph_unavailable", "FalkorDB is unavailable", 503) from exc
            message = str(exc).lower()
            if "no such graph" in message or "invalid graph" in message or "empty key" in message:
                return
            raise
