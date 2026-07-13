"""Unit tests for the password hashing and access-token primitives."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from domain import auth
from domain.models import Role


def test_hash_password_is_verifiable_and_not_plaintext():
    hashed = auth.hash_password("hunter2")

    assert hashed != "hunter2"
    assert auth.verify_password("hunter2", hashed)
    assert not auth.verify_password("wrong", hashed)


def test_access_token_round_trips_id_and_role():
    token = auth.create_access_token(7, Role.ADMIN, secret="s3cret", expires_minutes=60)

    user_id, role = auth.decode_access_token(token, "s3cret")

    assert user_id == 7
    assert role is Role.ADMIN


def test_decode_rejects_wrong_secret():
    token = auth.create_access_token(1, Role.OPERATOR, secret="right", expires_minutes=60)

    with pytest.raises(auth.InvalidToken):
        auth.decode_access_token(token, "wrong")


def test_decode_rejects_expired_token():
    past = datetime(2020, 1, 1, tzinfo=timezone.utc)
    token = auth.create_access_token(1, Role.ADMIN, secret="s", expires_minutes=1, now=past)

    with pytest.raises(auth.InvalidToken):
        auth.decode_access_token(token, "s")


def test_decode_rejects_garbage():
    with pytest.raises(auth.InvalidToken):
        auth.decode_access_token("not-a-jwt", "s")
