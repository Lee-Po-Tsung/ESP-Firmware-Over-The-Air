"""Tests for the lazy JWT secret in Settings.

Key generation, TLS certs and alembic all import config before `.env` exists,
so constructing Settings must not require JWT_SECRET; only touching
`jwt_secret` (as the server does at boot) may fail.
"""

from __future__ import annotations

import pytest
from config import Settings


def test_settings_constructs_without_jwt_secret(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)

    settings = Settings()

    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        _ = settings.jwt_secret


def test_jwt_secret_read_from_env(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "from-env")

    assert Settings().jwt_secret == "from-env"
