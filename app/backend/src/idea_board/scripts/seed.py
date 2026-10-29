"""Insert a few sample ideas - ONLY if the table is empty (local development seed data).

WHY:   A fresh local stack should show a non-empty board so you can see the UI work
       immediately (capability requirement: "local seed data").
SAFETY: idempotent and non-destructive - it never deletes or duplicates. It also refuses
       to run when APP_ENV is staging/prod, so it can never pollute real data.
HOW TO RUN: uv run idea-board-seed     (compose: `docker compose --profile tools run seed`)
"""

from __future__ import annotations

import sys

from sqlalchemy import func, insert, select

from idea_board.core.logging import configure_logging, get_logger
from idea_board.core.secrets import load_db_credentials
from idea_board.core.settings import Settings
from idea_board.db.engine import create_db_engine
from idea_board.db.tables import ideas

log = get_logger(__name__)

SAMPLE_IDEAS = [
    "Run the same container image on AWS and GCP",
    "Let AI explain why the CI pipeline failed",
    "Roll back automatically when the error rate spikes",
]

_FORBIDDEN_ENVS = {"staging", "prod", "production"}


def main() -> int:
    settings = Settings()
    configure_logging(settings.log_level, settings.log_pretty)
    if settings.app_env.lower() in _FORBIDDEN_ENVS:
        log.error("seed_refused", app_env=settings.app_env)
        return 1
    engine = create_db_engine(load_db_credentials(settings), settings)
    try:
        with engine.begin() as conn:
            count = conn.execute(select(func.count()).select_from(ideas)).scalar_one()
            if count:
                log.info("seed_skipped", existing_rows=count)
                return 0
            conn.execute(insert(ideas), [{"content": c} for c in SAMPLE_IDEAS])
            log.info("seed_inserted", rows=len(SAMPLE_IDEAS))
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(main())
