"""HTTP routes: the spec's two endpoints + the approved operational extras.

SPEC (frozen contract, do not change without approval):
  GET  /api/ideas  -> 200, JSON array of ALL ideas
  POST /api/ideas  -> accepts {"content": "..."} and stores it (we return 201 + the idea)
APPROVED NON-BREAKING EXTRAS (Phase 0, Q15):
  GET /healthz  liveness  - "is the process alive?"   (never touches the DB)
  GET /readyz   readiness - "can I serve traffic?"    (DB answers SELECT 1)
  GET /metrics  Prometheus metrics
  GET /api/version  running image tag (e.g. 1.1.0-a1b2c3d-42) - confirms which release is live
  /docs, /openapi.json are provided by FastAPI itself.

WHY sync `def` handlers (not `async def`)?
  psycopg/SQLAlchemy calls here are blocking. FastAPI runs plain `def` endpoints in a
  worker thread pool, so a slow query never blocks the event loop.
  SCALE NOTE: at very high concurrency an async driver + `async def` avoids thread-pool
  limits; at our scale (and with HPA adding pods) sync is simpler and fast enough.

WHY liveness never checks the DB?
  IF the DB has an outage AND liveness checked it THEN Kubernetes would restart every
  backend pod in a loop (restarts don't fix the DB) - a self-inflicted outage amplifier.
  Readiness instead removes pods from load balancing until the DB is back.
LEARN: docs/learning/10-backend-python-fastapi.md §3
"""

from __future__ import annotations

import random
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import Engine

from idea_board.api.errors import FaultInjectedError, error_response
from idea_board.api.schemas import ErrorResponse, IdeaCreate, IdeaOut
from idea_board.core import metrics
from idea_board.core.logging import get_logger
from idea_board.db import repository

log = get_logger(__name__)

router = APIRouter()


def get_engine(request: Request) -> Engine:
    """Dependency: the process-wide Engine created at startup (see main.lifespan).

    Using FastAPI dependency injection lets tests swap the engine without monkeypatching.
    """
    engine: Engine = request.app.state.engine
    return engine


EngineDep = Annotated[Engine, Depends(get_engine)]


def inject_fault(request: Request) -> None:
    """Demo fault injection (ADR-038): fail this fraction of /api requests with HTTP 500.

    A route DEPENDENCY (not middleware) so it runs after routing: injected errors are counted
    under their real route template (route="/api/ideas") and the health gate sees them.
    Default rate 0 = never fires. `random` is fine: a traffic sampler, not cryptography.
    """
    rate: float = request.app.state.settings.fault_injection_rate
    if rate > 0 and random.random() < rate:  # noqa: S311
        raise FaultInjectedError


FaultDep = Depends(inject_fault)


@router.get(
    "/api/ideas",
    response_model=list[IdeaOut],
    summary="List all ideas (newest first)",
    responses={503: {"model": ErrorResponse}},
    dependencies=[FaultDep],
)
def list_ideas(engine: EngineDep) -> list[IdeaOut]:
    return [IdeaOut(**row) for row in repository.list_ideas(engine)]


@router.post(
    "/api/ideas",
    response_model=IdeaOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create an idea",
    responses={422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    dependencies=[FaultDep],
)
def create_idea(payload: IdeaCreate, engine: EngineDep) -> IdeaOut:
    row = repository.create_idea(engine, payload.content)
    # Log the fact, not the content (privacy: idea text is user data).
    log.info("idea_created", idea_id=row["id"], content_length=len(row["content"]))
    return IdeaOut(**row)


@router.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/version", include_in_schema=False)  # under /api so the ingress routes it here
def version(request: Request) -> dict[str, str]:
    return {"version": request.app.state.settings.app_version}


@router.get("/readyz", include_in_schema=False, response_model=None)
def readyz(engine: EngineDep) -> dict[str, str] | JSONResponse:
    try:
        repository.ping(engine)
    except Exception as exc:  # any failure = not ready; the reason goes to logs only
        log.warning("readiness_failed", error_type=type(exc).__name__)
        return error_response(503, "not_ready", "Database not reachable.")
    return {"status": "ready"}


@router.get("/metrics", include_in_schema=False)
def metrics_endpoint() -> Response:
    body, content_type = metrics.render_latest()
    return Response(content=body, media_type=content_type)
