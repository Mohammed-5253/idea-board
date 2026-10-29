"""SPEC CONTRACT GUARDS: fail the build if the API or table drift from the specification.

  * "a single ideas table (id, content, created_at)"
  * "GET /api/ideas: Returns a JSON array of all ideas."
  * "POST /api/ideas: Accepts a JSON object like {"content": "My new idea"} and stores it."
Changing these tests requires the project owner's approval (USR-PR-02).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, inspect

pytestmark = [pytest.mark.contract, pytest.mark.integration]


def test_ideas_table_has_exactly_the_spec_columns(pg_engine: Engine) -> None:
    cols = {c["name"]: c for c in inspect(pg_engine).get_columns("ideas")}
    assert list(cols) == ["id", "content", "created_at"]
    assert str(cols["id"]["type"]) == "BIGINT"
    assert str(cols["content"]["type"]) == "TEXT"
    assert "TIMESTAMP" in str(cols["created_at"]["type"])
    assert all(not c["nullable"] for c in cols.values())


def test_get_without_parameters_returns_a_json_array_of_all_ideas(client: TestClient) -> None:
    for i in range(25):
        client.post("/api/ideas", json={"content": f"idea {i}"})
    r = client.get("/api/ideas")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) == 25  # ALL ideas, no implicit page size


def test_post_accepts_the_spec_example_and_stores_it(client: TestClient) -> None:
    r = client.post("/api/ideas", json={"content": "My new idea"})
    assert r.status_code == 201
    assert client.get("/api/ideas").json()[0]["content"] == "My new idea"
