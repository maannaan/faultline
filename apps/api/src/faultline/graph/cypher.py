"""Parameterized Cypher execution."""

from __future__ import annotations

from typing import Any

from faultline.errors import FaultlineError

_CONNECTION_TYPES = {"ConnectionError", "TimeoutError", "BusyLoadingError"}


def is_connection_error(exc: BaseException) -> bool:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if current.__class__.__name__ in _CONNECTION_TYPES:
            return True
        current = current.__cause__ or current.__context__
    return False


def run(graph: Any, statement: str, params: dict[str, Any] | None = None) -> Any:
    try:
        return graph.query(statement, params or {})
    except Exception as exc:
        if is_connection_error(exc):
            raise FaultlineError("graph_unavailable", "FalkorDB is unavailable", 503) from exc
        raise


def _column_name(column: Any) -> str:
    if isinstance(column, (list, tuple)):
        names = [item for item in column if isinstance(item, str)]
        if names:
            return names[0]
        return str(column[-1])
    return str(column)


def records(result: Any) -> list[dict[str, Any]]:
    header = [_column_name(column) for column in (getattr(result, "header", None) or [])]
    rows: list[dict[str, Any]] = []
    for row in getattr(result, "result_set", None) or []:
        if header and len(header) == len(row):
            rows.append(dict(zip(header, row, strict=True)))
        elif isinstance(row, dict):
            rows.append(row)
        else:
            rows.append({str(index): value for index, value in enumerate(row)})
    return rows


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return [str(value)]
