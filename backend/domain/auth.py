"""Password hashing and access-token logic for dashboard accounts.

Passwords are bcrypt-hashed; access tokens are stateless JWTs carrying the
account id and role. The signing secret and lifetime are passed in from config
so this module stays free of environment lookups and easy to test.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from domain.models import Role

JWT_ALGORITHM = "HS256"


def hash_password(plaintext: str) -> str:
    """Return a bcrypt hash of the password, safe to store."""
    return bcrypt.hashpw(plaintext.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plaintext: str, password_hash: str) -> bool:
    """Check a plaintext password against a stored bcrypt hash."""
    return bcrypt.checkpw(plaintext.encode("utf-8"), password_hash.encode("utf-8"))


class InvalidToken(Exception):
    """Raised when an access token is missing, malformed, or expired."""


def create_access_token(
    user_id: int, role: Role, secret: str, expires_minutes: int, now: datetime | None = None
) -> str:
    """Mint a signed JWT with the account id as subject and role as a claim."""
    issued_at = now or datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role.value,
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, secret: str) -> tuple[int, Role]:
    """Verify a token and return its (user_id, role). Raises InvalidToken on failure."""
    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
        return int(payload["sub"]), Role(payload["role"])
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise InvalidToken(str(exc)) from exc
