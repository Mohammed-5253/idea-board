"""Integration tests: the HTTP API against a REAL PostgreSQL 17 (Testcontainers)."""

from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from idea_board.core.secrets import DbCredentials
from idea_board.core.settings import Settings
from idea_board.db.engine import create_db_engine
from idea_board.main import create_app

pytestmark = pytest.mark.integration


def test_post_returns_201_and_the_stored_idea(client: TestClient) -> None:
    r = client.post("/api/ideas", json={"content": "  My new idea  "})
    assert r.status_code == 201
    body = r.json()
    assert set(body) == {"id", "content", "created_at"}
    assert body["content"] == "My new idea"  # trimmed
    assert isinstance(body["id"], int)
    assert datetime.fromisoformat(body["created_at"]).tzinfo is not None


def test_get_returns_all_ideas_newest_first(client: TestClient) -> None:
    for text in ("first", "second", "third"):
        assert client.post("/api/ideas", json={"content": text}).status_code == 201
    r = client.get("/api/ideas")
    assert r.status_code == 200
    assert [i["content"] for i in r.json()] == ["third", "second", "first"]


def test_validation_error_has_consistent_shape(client: TestClient) -> None:
    r = client.post("/api/ideas", json={"content": ""})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "validation_error"
    assert err["details"][0]["field"] == "content"


def test_malformed_json_is_422(client: TestClient) -> None:
    r = client.post(
        "/api/ideas", content=b"{not json", headers={"Content-Type": "application/json"}
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_sql_injection_payload_is_stored_as_plain_text(client: TestClient) -> None:
    payload = "x'); DROP TABLE ideas; --"
    assert client.post("/api/ideas", json={"content": payload}).status_code == 201
    assert client.get("/api/ideas").json()[0]["content"] == payload  # table still exists


def test_unknown_route_uses_error_shape(client: TestClient) -> None:
    r = client.get("/api/nope")
    assert r.status_code == 404
    assert r.json() == {"error": {"code": "not_found", "message": "Not Found", "details": []}}


def test_health_ready_and_metrics(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json() == {"status": "ready"}
    client.get("/api/ideas")
    text = client.get("/metrics").text
    assert "http_server_requests_total" in text
    assert 'route="/api/ideas"' in text


def test_request_id_is_echoed(client: TestClient) -> None:
    r = client.get("/api/ideas", headers={"X-Request-ID": "abc-123"})
    assert r.headers["X-Request-ID"] == "abc-123"


def test_fault_injection_returns_500_when_enabled(clean_db, test_settings: Settings) -> None:  # type: ignore[no-untyped-def]
    app = create_app(
        test_settings.model_copy(update={"fault_injection_rate": 1.0}), engine=clean_db
    )
    with TestClient(app) as c:
        r = c.get("/api/ideas")
        assert r.status_code == 500
        assert r.json()["error"]["code"] == "fault_injected"
        assert c.get("/healthz").status_code == 200  # only /api/* is affected


def test_readyz_is_503_and_liveness_ok_when_db_unreachable(test_settings: Settings) -> None:
    bad = DbCredentials(
        host="127.0.0.1", port=9, dbname="x", user="x", password=SecretStr("x"), sslmode="disable"
    )
    engine = create_db_engine(bad, test_settings.model_copy(update={"db_connect_timeout_s": 1}))
    with TestClient(create_app(test_settings, engine=engine)) as c:
        assert c.get("/healthz").status_code == 200
        assert c.get("/readyz").status_code == 503
        r = c.get("/api/ideas")
        assert r.status_code == 503
        assert r.json()["error"]["code"] == "database_unavailable"


def test_fault_injected_errors_are_labelled_with_their_route(
    clean_db, test_settings: Settings
) -> None:  # type: ignore[no-untyped-def]
    """Regression (Phase 8): injected 500s must count under route=/api/ideas for the gate."""
    app = create_app(
        test_settings.model_copy(update={"fault_injection_rate": 1.0}), engine=clean_db
    )
    with TestClient(app) as c:
        c.get("/api/ideas")
        text = c.get("/metrics").text
    assert any(
        line.startswith("http_server_requests_total")
        and 'route="/api/ideas"' in line
        and 'status="500"' in line
        for line in text.splitlines()
    )


def test_latency_histogram_uses_second_buckets(client: TestClient) -> None:
    """Regression (Phase 8): default OTel buckets are milliseconds; ours must be seconds."""
    client.get("/api/ideas")
    text = client.get("/metrics").text
    assert "http_server_request_duration_seconds_bucket{" in text
    assert 'le="0.005"' in text and 'le="0.5"' in text
