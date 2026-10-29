"""Idea Board backend package.

WHAT:  The Python package behind the spec's REST API (`GET/POST /api/ideas`).
WHY:   Spec Part 1 asks for "A Python (FastAPI is recommended) application providing
       a simple REST API". Everything the API needs lives under this package:
         core/     settings, logging, metrics, secrets (cross-cutting concerns)
         db/       table definition, engine, queries (the data tier)
         api/      HTTP schemas, routes, error handling (the presentation of the API)
         scripts/  one-shot programs: seed data, DB role bootstrap
WHERE: Runs as one Uvicorn process per container/pod (ADR-012). Kubernetes scales pods.
HOW:   uv run uvicorn idea_board.main:app --reload       (local, outside containers)
LEARN: docs/learning/10-backend-python-fastapi.md
"""

# Single place for the version string; exposed in OpenAPI docs and logs.
__version__ = "0.1.0"
