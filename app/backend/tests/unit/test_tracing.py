"""Tracing is opt-in: disabled without an endpoint, enabled (and instrumenting) with one."""

from __future__ import annotations

import pytest
from fastapi import FastAPI

from idea_board.core.tracing import configure_tracing


def test_disabled_without_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    assert configure_tracing(FastAPI()) is False


def test_enabled_with_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    # Port 9 (discard): nothing listens; the BatchSpanProcessor exports asynchronously, so
    # enabling tracing must never block or fail the app when the collector is down.
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://127.0.0.1:9")
    app = FastAPI()
    assert configure_tracing(app) is True
    assert getattr(app, "_is_instrumented_by_opentelemetry", False) is True
