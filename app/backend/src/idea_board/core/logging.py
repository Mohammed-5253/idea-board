"""Structured (JSON) logging with structlog.

WHAT:  Configures every log line as one JSON object on stdout, e.g.
       {"ts": "...", "level": "info", "event": "request", "route": "/api/ideas",
        "status": 201, "duration_ms": 4.2, "request_id": "..."}
WHY:   (1) Machines read our logs: the OTel Collector ships them to Grafana Cloud, and
       the F1 AI health analyst reads them after a bad deploy. JSON needs no regex parsing.
       (2) 12-factor, factor XI: logs are an event stream on stdout; the platform routes it.
       We never write log files inside the container.
SECURITY NOTE: we never log idea content, request bodies, credentials or client IPs
       (docs/architecture/08-observability.md §2). The OTel Collector redaction processor
       is a second line of defence, not the first.
ALTERNATIVE: stdlib `logging` + a JSON formatter - one dependency fewer, clumsier API.
COMMON MISTAKE: calling `logging.basicConfig()` elsewhere → duplicate, non-JSON lines.
LEARN: docs/learning/10-backend-python-fastapi.md §3 (logging)
"""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(level: str = "INFO", pretty: bool = False) -> None:
    """Configure structlog AND the stdlib root logger to emit the same format.

    Why both? Libraries (Uvicorn, SQLAlchemy, Alembic) use stdlib `logging`. Routing them
    through structlog's ProcessorFormatter gives ONE consistent JSON stream.
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,  # adds request_id bound by middleware
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,  # exceptions become a string field
    ]

    renderer: structlog.types.Processor = (
        structlog.dev.ConsoleRenderer() if pretty else structlog.processors.JSONRenderer()
    )

    structlog.configure(
        processors=[*shared_processors, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
        )
    )

    root = logging.getLogger()
    root.handlers = [handler]  # replace (not append) → idempotent if called twice
    root.setLevel(level.upper())

    # Uvicorn's own access log would duplicate our request middleware log line
    # (and print client IPs). We emit a richer access event ourselves.
    logging.getLogger("uvicorn.access").disabled = True
    # SQLAlchemy echoes SQL at INFO when misconfigured; keep it at WARNING.
    # IF you need to debug SQL locally THEN set LOG_LEVEL=DEBUG temporarily.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Typed accessor so modules do `log = get_logger(__name__)`."""
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
