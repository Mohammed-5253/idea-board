# Idea Board backend

FastAPI service over PostgreSQL (SQLAlchemy, Alembic migrations).

| Endpoint | Purpose |
|---|---|
| `GET /api/ideas`, `POST /api/ideas` | list and create ideas |
| `GET /api/version` | running image tag (`APP_VERSION`, set at build time by CI) |
| `GET /healthz`, `GET /readyz` | liveness and readiness (readiness checks the DB) |
| `GET /metrics` | Prometheus metrics |

## Develop

```sh
uv sync
uv run ruff check .
uv run pytest tests/unit          # what CI runs
uv run pytest tests/integration   # needs Docker (testcontainers PostgreSQL)
```

The whole stack (DB, migrations, Dapr sidecar, frontend) runs from the repo root with
`docker compose up --build`.

## Configuration

Every field in `src/idea_board/core/settings.py` is read from the UPPER_CASE environment
variable of the same name, for example `DB_HOST`, `LOG_LEVEL` or `APP_VERSION`.
Database credentials come from env vars or from a Dapr secret store
(`DB_CREDENTIALS_SOURCE`).

Console scripts: `idea-board-db-bootstrap` creates the app role, and `idea-board-seed`
adds sample data.
