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
`docker compose up --build`. Dapr is used only there; on EKS/GKE the credentials come
from env vars (Kubernetes Secrets written by terraform).

## Configuration

Every field in `src/idea_board/core/settings.py` is read from the UPPER_CASE environment
variable of the same name, for example `DB_HOST`, `LOG_LEVEL` or `APP_VERSION`.
Database credentials come from env vars (`DB_CREDENTIALS_SOURCE=env`, used on EKS/GKE) or
from a Dapr secret store (`dapr`, local docker compose only).

Console scripts: `idea-board-db-bootstrap` creates the app role (in the cloud it runs in
the `db-migrate` Job with `BOOTSTRAP_OWNER_USER/PASSWORD`), and `idea-board-seed` adds
sample data.
