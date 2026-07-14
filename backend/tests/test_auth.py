"""Unit tests for the password hashing and access-token primitives."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from domain import auth
from domain.models import Role

# 32+ bytes each, matching RFC 7518's minimum HMAC key length for HS256.
SECRET = "unit-test-secret-0123456789abcdef"
WRONG_SECRET = "another-secret-0123456789abcdef!"


def test_hash_password_is_verifiable_and_not_plaintext():
    hashed = auth.hash_password("hunter2")

    assert hashed != "hunter2"
    assert auth.verify_password("hunter2", hashed)
    assert not auth.verify_password("wrong", hashed)


def test_verify_password_reports_mismatch_for_overlong_input():
    # bcrypt raises past 72 bytes; a login attempt must get False, not a 500.
    hashed = auth.hash_password("hunter2")

    assert not auth.verify_password("x" * (auth.MAX_PASSWORD_BYTES + 1), hashed)


def test_access_token_round_trips_id_and_role():
    token = auth.create_access_token(7, Role.ADMIN, secret=SECRET, expires_minutes=60)

    user_id, role = auth.decode_access_token(token, SECRET)

    assert user_id == 7
    assert role is Role.ADMIN


def test_decode_rejects_wrong_secret():
    token = auth.create_access_token(1, Role.OPERATOR, secret=SECRET, expires_minutes=60)

    with pytest.raises(auth.InvalidToken):
        auth.decode_access_token(token, WRONG_SECRET)


def test_decode_rejects_expired_token():
    past = datetime(2020, 1, 1, tzinfo=timezone.utc)
    token = auth.create_access_token(1, Role.ADMIN, secret=SECRET, expires_minutes=1, now=past)

    with pytest.raises(auth.InvalidToken):
        auth.decode_access_token(token, SECRET)


def test_decode_rejects_garbage():
    with pytest.raises(auth.InvalidToken):
        auth.decode_access_token("not-a-jwt", SECRET)
