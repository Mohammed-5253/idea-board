"""Consistent error responses for every failure mode.

WHAT:  Exception handlers that convert errors into ONE JSON shape:
         {"error": {"code": "...", "message": "...",
                    "details": [{"field": "...", "message": "..."}]}}
WHY:   Clients (the React app, tests, the AI CI explainer) can handle errors generically.
       FastAPI's default 422 body has a different shape from its 404/500 bodies - we unify.

Mapping:
  RequestValidationError (bad JSON / failed Pydantic rules) -> 422 validation_error
  StarletteHTTPException (404 unknown route, 405 wrong method) -> same status, code from status
  SQLAlchemy OperationalError / DBAPI errors (DB down, timeout) -> 503 database_unavailable
  Anything else -> 500 internal_error (details hidden; full traceback goes to the log)

SECURITY NOTE: never echo exception messages or SQL to clients (information disclosure);
       the client gets a generic message + the request_id to correlate with server logs.
LEARN: docs/learning/10-backend-python-fastapi.md §3
"""

from __future__ import annotations

from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from idea_board.api.schemas import ErrorBody, ErrorDetail, ErrorResponse
from idea_board.core.logging import get_logger

log = get_logger(__name__)


class FaultInjectedError(Exception):
    """Raised by the demo fault injector (ADR-038); rendered as HTTP 500 fault_injected."""


def error_response(
    status: int, code: str, message: str, details: list[ErrorDetail] | None = None
) -> JSONResponse:
    """Build a JSONResponse in the standard error shape."""
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details or []))
    return JSONResponse(status_code=status, content=body.model_dump())


def _field_path(loc: tuple[int | str, ...]) -> str:
    # Pydantic locations look like ("body", "content"); drop the "body"/"query" prefix.
    parts = [str(p) for p in loc if p not in ("body", "query", "path")]
    return ".".join(parts) or "body"


async def _validation_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)
    details = [
        ErrorDetail(field=_field_path(tuple(e.get("loc", ()))), message=str(e.get("msg", "")))
        for e in exc.errors()
    ]
    return error_response(422, "validation_error", "Request validation failed.", details)


async def _http_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    phrase = HTTPStatus(exc.status_code).phrase
    code = phrase.lower().replace(" ", "_")
    return error_response(exc.status_code, code, phrase)


async def _fault_handler(request: Request, exc: Exception) -> JSONResponse:
    log.warning("fault_injected", path=request.url.path)
    return error_response(500, "fault_injected", "Injected fault (demo mode).")


async def _db_handler(request: Request, exc: Exception) -> JSONResponse:
    # Log the real cause (for humans and the F1 analyst); return a generic 503.
    log.error("database_error", error_type=type(exc).__name__, path=request.url.path)
    return error_response(503, "database_unavailable", "The database is temporarily unavailable.")


async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled_error", error_type=type(exc).__name__, path=request.url.path)
    return error_response(500, "internal_error", "An unexpected error occurred.")


def register_error_handlers(app: FastAPI) -> None:
    """Attach all handlers to the app (called from create_app)."""
    app.add_exception_handler(FaultInjectedError, _fault_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(StarletteHTTPException, _http_handler)
    app.add_exception_handler(OperationalError, _db_handler)
    app.add_exception_handler(DBAPIError, _db_handler)
    app.add_exception_handler(Exception, _unhandled_handler)
