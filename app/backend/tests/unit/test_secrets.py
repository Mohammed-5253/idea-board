"""Unit tests for the credentials provider (DB_* env vars → DbCredentials)."""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from idea_board.core.secrets import CredentialsError, load_db_credentials
from idea_board.core.settings import Settings


def test_credentials_come_from_settings() -> None:
    creds = load_db_credentials(
        Settings(db_host="h", db_port=6543, db_user="u", db_password=SecretStr("p"))
    )
    assert (creds.host, creds.port, creds.user, creds.password.get_secret_value()) == (
        "h",
        6543,
        "u",
        "p",
    )


def test_missing_password_is_rejected() -> None:
    with pytest.raises(CredentialsError, match="DB_PASSWORD"):
        load_db_credentials(Settings(db_password=SecretStr("")))
