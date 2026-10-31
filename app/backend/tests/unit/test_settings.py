"""Unit tests for configuration validation (fail fast on bad config)."""

from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from idea_board.core.settings import Settings


def test_defaults_are_safe() -> None:
    s = Settings()
    assert s.fault_injection_rate == 0.0  # demo fault injection is OFF by default
    assert s.app_version == "dev"


@pytest.mark.parametrize("rate", [-0.1, 1.5])
def test_fault_injection_rate_bounds(rate: float) -> None:
    with pytest.raises(ValidationError):
        Settings(fault_injection_rate=rate)


def test_invalid_sslmode_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(db_sslmode="sometimes")


def test_password_never_in_repr() -> None:
    s = Settings(db_password=SecretStr("super-secret"))
    assert "super-secret" not in repr(s)
    assert "super-secret" not in str(s.model_dump())


def test_env_vars_are_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_HOST", "db.example")
    monkeypatch.setenv("DB_POOL_SIZE", "7")
    monkeypatch.setenv("APP_VERSION", "1.2.0-abc1234-9")
    s = Settings()
    assert s.db_host == "db.example"
    assert s.db_pool_size == 7
    assert s.app_version == "1.2.0-abc1234-9"
