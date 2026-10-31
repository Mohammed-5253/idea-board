"""Application factory and ASGI entry point.

WHAT:  `create_app()` builds the FastAPI app: logging, DB engine lifecycle, middleware,
       routes and error handlers. `app` at the bottom is what Uvicorn serves:
           uvicorn idea_board.main:app --host 0.0.0.0 --port 8000
WHY a factory?  Tests build isolated apps with their own Settings/Engine
       (`create_app(settings, engine)`), with no global state leaking between tests.

LIFECYCLE (lifespan):
  startup : load DB credentials (DB_* env vars) -> create the Engine (lazy, no connection yet)
  shutdown: dispose the pool (close connections cleanly so PostgreSQL doesn't log
            "unexpected EOF" and slots are freed immediately during rolling updates).
  IF the DB is down at startup THEN we still start (the engine is lazy): /healthz is OK,
  /readyz returns 503 until the DB answers. BUT in Kubernetes the readiness probe keeps the
  pod out of the load balancer meanwhile - exactly the behaviour we want.

MIDDLEWARE (outermost first):
  1. request context: request_id (from X-Request-ID or generated) bound into every log
     line; timing; one structured access-log event; metrics recorded with the route TEMPLATE.
  Fault injection (ADR-038) is NOT middleware: it is a dependency of the /api routes
  (api/routes.py), so it runs after routing and injected errors are labelled with their
  real route - the health gate must see them (bug found by the Phase 8 kind gate demo).
LEARN: docs/learning/10-backend-python-fastapi.md §3, §6
"""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response
from sqlalchemy import Engine

from idea_board import __version__
from idea_board.api.errors import register_error_handlers
from idea_board.api.routes import router
from idea_board.core import metrics
from idea_board.core.logging import configure_logging, get_logger
from idea_board.core.secrets import load_db_credentials
from idea_board.core.settings import Settings, get_settings
from idea_board.core.tracing import configure_tracing
from idea_board.db.engine import create_db_engine

log = get_logger(__name__)

# Upper bound for a client-supplied request id: prevents log-injection of huge values.
_MAX_REQUEST_ID_LEN = 128


def create_app(settings: Settings | None = None, engine: Engine | None = None) -> FastAPI:
    """Build the FastAPI application.

    settings: defaults to environment-derived settings.
    engine:   tests inject an Engine bound to a Testcontainers PostgreSQL; production
              leaves it None and the lifespan creates one from the credentials source.
    """
    cfg = settings or get_settings()
    configure_logging(cfg.log_level, cfg.log_pretty)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owns_engine = engine is None
        if engine is None:
            creds = load_db_credentials(cfg)
            app.state.engine = create_db_engine(creds, cfg)
            log.info(
                "startup",
                version=__version__,
                env=cfg.app_env,
                db_host=creds.host,
                db_name=creds.dbname,
                fault_injection_rate=cfg.fault_injection_rate,
            )
        else:
            app.state.engine = engine
        try:
            yield
        finally:
            if owns_engine:
                app.state.engine.dispose()
            log.info("shutdown")

    app = FastAPI(
        title="Idea Board API",
        version=__version__,
        description="Spec contract: GET /api/ideas (all ideas), POST /api/ideas {content}.",
        lifespan=lifespan,
    )
    app.state.settings = cfg

    register_error_handlers(app)
    app.include_router(router)
    configure_tracing(app)  # no-op unless OTEL_EXPORTER_OTLP_ENDPOINT is set

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming[:_MAX_REQUEST_ID_LEN] if incoming else uuid.uuid4().hex
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            duration = time.perf_counter() - start
            # Route TEMPLATE (bounded cardinality) - "unmatched" for 404s.
            route_obj = request.scope.get("route")
            route = getattr(route_obj, "path", "unmatched")
            if route != "/metrics":  # don't measure the scraper itself
                metrics.record_request(request.method, route, status, duration)
                log.info(
                    "request",
                    method=request.method,
                    route=route,
                    status=status,
                    duration_ms=round(duration * 1000, 2),
                )

    return app


# ASGI entry point for Uvicorn. Settings come from the environment.
app = create_app()
