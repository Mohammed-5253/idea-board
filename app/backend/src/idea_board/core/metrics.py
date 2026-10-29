"""HTTP metrics with the OpenTelemetry SDK, exposed in Prometheus format on /metrics.

WHAT:  Two instruments, recorded by the request middleware in main.py:
         http_server_requests_total{method, route, status}          (counter)
         http_server_request_duration_seconds{method, route, status} (histogram)
WHY:   The deterministic health gate (ADR-001/024) and dashboards need request rate,
       error ratio and latency per route. Resolution of AD-13 (ADR-040): we use the
       OTel SDK + its Prometheus exporter, ONE ecosystem that also gives us traces later.
       Envoy also reports these at the edge; app-level metrics add the route template
       and work locally (docker-compose) where there is no Envoy.
SCALE NOTE: label cardinality is bounded on purpose: `route` is the route TEMPLATE
       (e.g. "/api/ideas"), never the raw path, so unknown paths cannot explode the series
       count (a classic Prometheus outage cause).
ALTERNATIVE: prometheus-client directly - simpler, but a second metrics ecosystem.
COMMON MISTAKE: creating a new MeterProvider per app instance → "duplicate timeseries"
       errors; we initialise exactly once per process (see `_init_once`).
COMMON MISTAKE (found by the Phase 8 health-gate demo): the OTel SDK's DEFAULT histogram
       buckets (0, 5, 10, 25 ... 10000) are designed for MILLISECONDS. We record SECONDS, so
       every request (~0.005 s) fell into the first bucket [0, 5] and Prometheus estimated
       p95 = 4.75 s for a healthy service. Explicit second-based boundaries fix it.
LEARN: docs/learning/10-backend-python-fastapi.md §3, observability doc in Phase 8.
"""

from __future__ import annotations

import threading

from opentelemetry import metrics
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from idea_board import __version__

# Seconds. Dense around the gate threshold (0.5 s) so p95 estimates are precise there.
LATENCY_BUCKETS_S = [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 10.0]

_lock = threading.Lock()
_instruments: tuple[metrics.Counter, metrics.Histogram] | None = None


def _init_once() -> tuple[metrics.Counter, metrics.Histogram]:
    """Create the MeterProvider + instruments exactly once per process (thread-safe)."""
    global _instruments
    with _lock:
        if _instruments is None:
            # The Prometheus reader registers itself with prometheus_client's default
            # registry; `generate_latest()` below renders that registry.
            reader = PrometheusMetricReader()
            provider = MeterProvider(
                resource=Resource.create({SERVICE_NAME: "idea-board-backend"}),
                metric_readers=[reader],
            )
            metrics.set_meter_provider(provider)
            meter = metrics.get_meter("idea_board", __version__)
            requests = meter.create_counter(
                "http_server_requests", unit="1", description="HTTP requests handled"
            )
            duration = meter.create_histogram(
                "http_server_request_duration",
                unit="s",
                description="HTTP request duration",
                explicit_bucket_boundaries_advisory=LATENCY_BUCKETS_S,
            )
            _instruments = (requests, duration)
        return _instruments


def record_request(method: str, route: str, status: int, duration_s: float) -> None:
    """Record one finished HTTP request."""
    requests, duration = _init_once()
    attrs = {"method": method, "route": route, "status": str(status)}
    requests.add(1, attrs)
    duration.record(duration_s, attrs)


def render_latest() -> tuple[bytes, str]:
    """Return (body, content_type) for the /metrics endpoint."""
    _init_once()
    return generate_latest(), CONTENT_TYPE_LATEST
