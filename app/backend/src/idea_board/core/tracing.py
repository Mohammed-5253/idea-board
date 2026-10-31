"""Distributed tracing with OpenTelemetry (OTLP over HTTP to the in-cluster collector).

WHAT:  When OTEL_EXPORTER_OTLP_ENDPOINT is set (Kubernetes: http://otel-collector...:4318),
       every HTTP request becomes a span (FastAPI auto-instrumentation) and spans are batched
       to the OpenTelemetry Collector.
WHY OPT-IN?  Local runs, tests and docker-compose have no collector; exporting there would
       only produce connection errors. Unset endpoint = tracing fully disabled (zero cost).
CONFIG (standard OTel env vars, so ops can tune without code changes):
       OTEL_EXPORTER_OTLP_ENDPOINT   collector base URL (exporter appends /v1/traces)
       OTEL_SERVICE_NAME             default "idea-board-backend"
       OTEL_TRACES_SAMPLER(_ARG)     e.g. parentbased_traceidratio / 0.1 at high traffic
SECURITY NOTE: spans carry route templates, status codes and timings - never request
       bodies (idea content is user data and is not recorded).
SCALE NOTE: BatchSpanProcessor exports asynchronously; at 100x traffic lower the sampling
       ratio instead of dropping tracing.
LEARN: docs/learning/20-continuous-delivery-observability.md §3
"""

from __future__ import annotations

import os

from fastapi import FastAPI

from idea_board.core.logging import get_logger

log = get_logger(__name__)

_EXCLUDED_URLS = "healthz,readyz,metrics"  # probes and scrapes would drown real traffic


def configure_tracing(app: FastAPI) -> bool:
    """Instrument the app if an OTLP endpoint is configured. Returns True when enabled."""
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not endpoint:
        return False

    # Imported lazily so the exporter machinery is only loaded when tracing is on.
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    service = os.environ.get("OTEL_SERVICE_NAME", "idea-board-backend")
    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))  # reads OTEL_* env
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, excluded_urls=_EXCLUDED_URLS)
    log.info("tracing_enabled", endpoint=endpoint, service=service)
    return True
