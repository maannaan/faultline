"""FastAPI application."""

from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from faultline.config import Settings, get_settings
from faultline.errors import FaultlineError
from faultline.graph.client import GraphStore
from faultline.graph.cypher import is_connection_error
from faultline.llm import build_extractor
from faultline.llm.adapter import Extractor
from faultline.logging import correlation_id_var, setup_logging
from faultline.replay import build_answerer
from faultline.replay.service import Answerer
from faultline.routes import router


def create_app(
    settings: Settings | None = None,
    store: GraphStore | None = None,
    extractor: Extractor | None = None,
    answerer: Answerer | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.log_level)
    app = FastAPI(title="Faultline", version="0.1.0")
    app.state.settings = settings
    app.state.store = store or GraphStore(settings)
    app.state.extractor = extractor or build_extractor(settings)
    app.state.answerer = answerer or build_answerer(settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def correlation_middleware(request: Request, call_next):
        incoming = request.headers.get("x-correlation-id") or str(uuid.uuid4())
        request.state.correlation_id = incoming
        token = correlation_id_var.set(incoming)
        try:
            response = await call_next(request)
        finally:
            correlation_id_var.reset(token)
        response.headers["X-Correlation-ID"] = incoming
        return response

    @app.exception_handler(FaultlineError)
    async def handle_faultline(request: Request, exc: FaultlineError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(request, exc.code, exc.message),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content=_error_body(request, "validation_error", _validation_message(exc)),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        if is_connection_error(exc):
            return JSONResponse(
                status_code=503,
                content=_error_body(request, "graph_unavailable", "FalkorDB is unavailable"),
            )
        return JSONResponse(
            status_code=500,
            content=_error_body(request, "internal_error", "Internal error"),
        )

    app.include_router(router)
    return app


def _error_body(request: Request, code: str, message: str) -> dict[str, dict[str, str]]:
    correlation_id = getattr(request.state, "correlation_id", "") or correlation_id_var.get()
    return {"error": {"code": code, "message": message, "correlation_id": correlation_id}}


def _validation_message(exc: RequestValidationError) -> str:
    parts: list[str] = []
    for error in exc.errors():
        loc = ".".join(str(item) for item in error.get("loc", []) if item != "body")
        message = str(error.get("msg", "Invalid request"))
        parts.append(f"{loc}: {message}" if loc else message)
    return "; ".join(parts) or "Invalid request"


app = create_app()
