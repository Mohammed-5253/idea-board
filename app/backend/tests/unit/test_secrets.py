"""Unit tests for the credentials provider, including the Dapr secrets API path.

A tiny stdlib HTTP server plays the role of the Dapr sidecar, so these tests need neither
Dapr nor Docker - they verify OUR parsing and retry logic.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest
from pydantic import SecretStr

from idea_board.core.secrets import CredentialsError, load_db_credentials
from idea_board.core.settings import CredentialsSource, Settings


def _serve(status: int, body: Any) -> Iterator[int]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            payload = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args: object) -> None:  # keep test output quiet
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()


def _dapr_settings(port: int, **kw: Any) -> Settings:
    return Settings(
        db_credentials_source=CredentialsSource.DAPR,
        dapr_http_port=port,
        dapr_startup_timeout_s=1.0,
        **kw,
    )


def test_env_source_uses_settings() -> None:
    creds = load_db_credentials(Settings(db_host="h", db_user="u", db_password=SecretStr("p")))
    assert (creds.host, creds.user, creds.password.get_secret_value()) == ("h", "u", "p")


@pytest.fixture
def multi_key_sidecar() -> Iterator[int]:
    yield from _serve(
        200,
        {"username": "app", "password": "pw", "host": "db", "port": "6543", "dbname": "ideas_prod"},
    )


def test_dapr_multi_key_shape(multi_key_sidecar: int) -> None:
    creds = load_db_credentials(_dapr_settings(multi_key_sidecar))
    assert (creds.user, creds.host, creds.port, creds.dbname) == ("app", "db", 6543, "ideas_prod")
    assert creds.password.get_secret_value() == "pw"


@pytest.fixture
def single_value_sidecar() -> Iterator[int]:
    # AWS Secrets Manager / GCP Secret Manager shape: {secret-name: "<json string>"}
    inner = json.dumps({"username": "app", "password": "pw2", "host": "10.0.0.5"})
    yield from _serve(200, {"idea-board-db-app": inner})


def test_dapr_single_value_json_shape(single_value_sidecar: int) -> None:
    creds = load_db_credentials(_dapr_settings(single_value_sidecar, db_name="fallback_db"))
    assert creds.host == "10.0.0.5"
    assert creds.dbname == "fallback_db"  # missing key falls back to plain settings
    assert creds.password.get_secret_value() == "pw2"


@pytest.fixture
def not_found_sidecar() -> Iterator[int]:
    yield from _serve(404, {"errorCode": "ERR_SECRET_GET"})


def test_dapr_4xx_fails_fast(not_found_sidecar: int) -> None:
    with pytest.raises(CredentialsError, match="HTTP 404"):
        load_db_credentials(_dapr_settings(not_found_sidecar))


def test_dapr_unreachable_times_out() -> None:
    # Port 9 (discard) on localhost: nothing listens → connection refused → retries → error.
    with pytest.raises(CredentialsError, match="not reachable"):
        load_db_credentials(_dapr_settings(9))


@pytest.fixture
def no_password_sidecar() -> Iterator[int]:
    yield from _serve(200, {"username": "app"})


def test_secret_without_password_is_rejected(no_password_sidecar: int) -> None:
    with pytest.raises(CredentialsError):
        load_db_credentials(_dapr_settings(no_password_sidecar))
