"""Tests for GET/PATCH /api/ideas/{id} (optimistic concurrency) and the DB side.

"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import DBAPIError

from idea_board.core.secrets import DbCredentials
from idea_board.core.settings import Settings
from idea_board.db.engine import create_db_engine
from idea_board.main import create_app
from idea_board.scripts.db_bootstrap import bootstrap
from tests.conftest import run_alembic

pytestmark = pytest.mark.integration


def _wipe(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE ideas RESTART IDENTITY CASCADE"))


@pytest.fixture
def db(pg_engine: Engine) -> Iterator[Engine]:
    run_alembic(pg_engine, "upgrade", "head")
    _wipe(pg_engine)
    yield pg_engine
    _wipe(pg_engine)


@pytest.fixture
def api(db: Engine, test_settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(test_settings, engine=db)) as c:
        yield c


def _app_creds(owner: DbCredentials) -> DbCredentials:
    return DbCredentials(
        host=owner.host,
        port=owner.port,
        dbname=owner.dbname,
        user="ideas_app",
        password=SecretStr("app-pass"),
        sslmode="disable",
    )


def _assert_error(r, status: int) -> None:  # type: ignore[no-untyped-def]
    assert r.status_code == status, (r.status_code, r.text)
    body = r.json()
    assert set(body) == {"error"}, body
    assert isinstance(body["error"]["code"], str) and isinstance(body["error"]["message"], str)
    assert isinstance(body["error"]["details"], list)


def _idea(c: TestClient, content: str) -> int:
    r = c.post("/api/ideas", json={"content": content})
    assert r.status_code == 201, r.text
    return int(r.json()["id"])


def _revisions(engine: Engine) -> list[dict]:
    with engine.connect() as conn:
        return [dict(r._mapping) for r in conn.execute(text("SELECT * FROM idea_revisions"))]


def test_post_returns_etag_and_unchanged_body(api: TestClient) -> None:
    r = api.post("/api/ideas", json={"content": "  first  "})
    assert r.status_code == 201
    assert r.headers["etag"] == '"1"'
    assert set(r.json()) == {"id", "content", "created_at"}
    assert r.json()["content"] == "first"


def test_get_one_idea(api: TestClient) -> None:
    idea_id = _idea(api, "hello")
    r = api.get(f"/api/ideas/{idea_id}")
    assert r.status_code == 200
    assert r.headers["etag"] == '"1"'
    listed = api.get("/api/ideas").json()
    assert r.json() == listed[0]
    _assert_error(api.get("/api/ideas/999999"), 404)


def test_edit_happy_path_and_versions(api: TestClient, db: Engine) -> None:
    older = _idea(api, "older")
    idea_id = _idea(api, "v1 text")
    created = api.get(f"/api/ideas/{idea_id}").json()

    r = api.patch(f"/api/ideas/{idea_id}", json={"content": "  v2 text "}, headers={"If-Match": '"1"'})
    assert r.status_code == 200, r.text
    assert r.headers["etag"] == '"2"'
    assert r.json() == {**created, "content": "v2 text"}

    r = api.patch(f"/api/ideas/{idea_id}", json={"content": "v3 text"}, headers={"If-Match": '"2"'})
    assert r.status_code == 200 and r.headers["etag"] == '"3"'
    g = api.get(f"/api/ideas/{idea_id}")
    assert g.headers["etag"] == '"3"' and g.json()["content"] == "v3 text"
    # Other ideas keep version 1; list keeps its fields and newest-first order.
    assert api.get(f"/api/ideas/{older}").headers["etag"] == '"1"'
    listed = api.get("/api/ideas").json()
    assert [i["id"] for i in listed] == [idea_id, older]
    assert all(set(i) == {"id", "content", "created_at"} for i in listed)

    # History: one row per edit with idea id, new version, previous content, edit time.
    rows = _revisions(db)
    assert len(rows) == 2
    for version, previous in ((2, "v1 text"), (3, "v2 text")):
        assert any(
            idea_id in row.values()
            and version in row.values()
            and previous in row.values()
            and any(isinstance(v, datetime) for v in row.values())
            for row in rows
        ), (version, rows)


def test_edit_errors_and_precedence(api: TestClient) -> None:
    idea_id = _idea(api, "x")
    # 422 first: invalid body, even for unknown ideas or missing If-Match.
    for body in ({}, {"content": ""}, {"content": "   "}, {"content": 5}, {"content": "a" * 501}):
        _assert_error(api.patch(f"/api/ideas/{idea_id}", json=body, headers={"If-Match": '"1"'}), 422)
        _assert_error(api.patch("/api/ideas/999999", json=body), 422)
    # then 404, then 428, then 412.
    _assert_error(api.patch("/api/ideas/999999", json={"content": "y"}), 404)
    _assert_error(api.patch("/api/ideas/999999", json={"content": "y"}, headers={"If-Match": '"1"'}), 404)
    _assert_error(api.patch(f"/api/ideas/{idea_id}", json={"content": "y"}), 428)
    for stale in ('"2"', '"0"', "1", 'W/"1"', '"abc"', "*", '""'):
        _assert_error(api.patch(f"/api/ideas/{idea_id}", json={"content": "y"}, headers={"If-Match": stale}), 412)
    g = api.get(f"/api/ideas/{idea_id}")
    assert g.json()["content"] == "x" and g.headers["etag"] == '"1"'


def test_concurrent_edits_one_winner(db: Engine, test_settings: Settings) -> None:
    app = create_app(test_settings, engine=db)
    with TestClient(app) as c:
        idea_id = _idea(c, "race v1")
    for round_ in range(5):
        etag = f'"{round_ + 1}"'
        barrier = threading.Barrier(8)
        results: list[tuple[int, str]] = []
        lock = threading.Lock()

        def hit(n: int) -> None:
            with TestClient(app) as client:
                barrier.wait()
                r = client.patch(
                    f"/api/ideas/{idea_id}", json={"content": f"r{round_} w{n}"}, headers={"If-Match": etag}
                )
                with lock:
                    results.append((r.status_code, r.json().get("content", "")))

        threads = [threading.Thread(target=hit, args=(n,)) for n in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        codes = sorted(code for code, _ in results)
        assert codes == [200] + [412] * 7, results
        winner = next(content for code, content in results if code == 200)
        with TestClient(app) as c:
            g = c.get(f"/api/ideas/{idea_id}")
            assert g.json()["content"] == winner
            assert g.headers["etag"] == f'"{round_ + 2}"'
    assert len(_revisions(db)) == 5


def test_ideas_table_columns_unchanged(db: Engine) -> None:
    cols = [c["name"] for c in inspect(db).get_columns("ideas")]
    assert cols == ["id", "content", "created_at"]


def _app_role_checks(owner: DbCredentials, test_settings: Settings) -> None:
    engine = create_db_engine(_app_creds(owner), test_settings)
    try:
        with TestClient(create_app(test_settings, engine=engine)) as c:
            idea_id = _idea(c, "by app role")
            r = c.patch(f"/api/ideas/{idea_id}", json={"content": "edited"}, headers={"If-Match": '"1"'})
            assert r.status_code == 200, r.text
            g = c.get(f"/api/ideas/{idea_id}")
            assert g.json()["content"] == "edited" and g.headers["etag"] == '"2"'
            assert c.get("/api/ideas").json()[0]["content"] == "edited"
        denied = [
            "UPDATE ideas SET created_at = created_at",
            "DELETE FROM ideas",
            "TRUNCATE ideas",
            "DELETE FROM idea_revisions",
            "TRUNCATE idea_revisions",
            "INSERT INTO alembic_version VALUES ('zzzz')",
        ]
        cols = [c["name"] for c in inspect(engine).get_columns("idea_revisions")]
        denied += [f"UPDATE idea_revisions SET {col} = {col}" for col in cols]
        for stmt in denied:
            with pytest.raises(DBAPIError, match="permission denied"), engine.begin() as conn:
                conn.execute(text(stmt))
        with pytest.raises(DBAPIError, match="permission denied|must be owner"), engine.begin() as conn:
            conn.execute(text("CREATE TABLE public.sneaky (x int)"))
        with engine.connect() as conn:  # still readable
            conn.execute(text("SELECT * FROM idea_revisions")).all()
    finally:
        engine.dispose()


def _drop_app_role(engine: Engine) -> None:
    """Back to an empty database without the app role (owner-created objects only)."""
    run_alembic(engine, "downgrade", "base")
    with engine.begin() as conn:
        if conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = 'ideas_app'")).first():
            conn.execute(text("DROP OWNED BY ideas_app"))
            conn.execute(text("DROP ROLE ideas_app"))


def test_app_role_bootstrap_before_migrations(
    pg_container: DbCredentials, pg_engine: Engine, test_settings: Settings
) -> None:
    """Fresh database: bootstrap first, then all migrations (the db-migrate Job order)."""
    _drop_app_role(pg_engine)
    bootstrap(pg_container, _app_creds(pg_container))
    run_alembic(pg_engine, "upgrade", "head")
    _app_role_checks(pg_container, test_settings)
    _wipe(pg_engine)


def test_app_role_bootstrap_after_migrations(
    pg_container: DbCredentials, pg_engine: Engine, test_settings: Settings
) -> None:
    """Database already migrated to head before the app role ever existed."""
    _drop_app_role(pg_engine)
    run_alembic(pg_engine, "upgrade", "head")
    bootstrap(pg_container, _app_creds(pg_container))
    bootstrap(pg_container, _app_creds(pg_container))  # idempotent
    _app_role_checks(pg_container, test_settings)
    _wipe(pg_engine)


def test_app_role_bootstrap_between_0001_and_head(
    pg_container: DbCredentials, pg_engine: Engine, test_settings: Settings
) -> None:
    """Database at 0001 (feature not yet deployed): bootstrap, then upgrade to head."""
    _drop_app_role(pg_engine)
    run_alembic(pg_engine, "upgrade", "0001")
    bootstrap(pg_container, _app_creds(pg_container))
    run_alembic(pg_engine, "upgrade", "head")
    _app_role_checks(pg_container, test_settings)
    _wipe(pg_engine)


def test_migration_downgrade_keeps_ideas(db: Engine, test_settings: Settings) -> None:
    with TestClient(create_app(test_settings, engine=db)) as c:
        idea_id = _idea(c, "v1")
        c.patch(f"/api/ideas/{idea_id}", json={"content": "survives"}, headers={"If-Match": '"1"'})
    assert inspect(db).has_table("idea_revisions")
    run_alembic(db, "downgrade", "0001")
    assert not inspect(db).has_table("idea_revisions")
    with db.connect() as conn:
        assert conn.execute(text("SELECT content FROM ideas")).scalars().all() == ["survives"]
    run_alembic(db, "upgrade", "head")
    assert inspect(db).has_table("idea_revisions")
    with TestClient(create_app(test_settings, engine=db)) as c:
        assert c.get(f"/api/ideas/{idea_id}").json()["content"] == "survives"
