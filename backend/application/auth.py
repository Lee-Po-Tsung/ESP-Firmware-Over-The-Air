"""Register accounts and authenticate logins.

`RegisterUser` hashes the password and stores the account. `AuthenticateUser`
checks a login and mints a JWT. Roles and hashing live in `domain/auth.py`; this
layer only wires the repository, the domain, and the config-supplied secret.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain import auth
from domain.models import Role, User
from ports.repository import UserRepository


@dataclass
class RegisterUserRequest:
    username: str
    password: str
    role: Role = Role.OPERATOR


class RegisterUser:
    def __init__(self, repository: UserRepository) -> None:
        self._repo = repository

    def execute(self, req: RegisterUserRequest) -> User:
        user = User(
            username=req.username,
            password_hash=auth.hash_password(req.password),
            role=req.role,
        )
        return self._repo.add(user)


class InvalidCredentials(Exception):
    """Raised when a login's username or password does not match."""


class AuthenticateUser:
    def __init__(self, repository: UserRepository, jwt_secret: str, expires_minutes: int) -> None:
        self._repo = repository
        self._jwt_secret = jwt_secret
        self._expires_minutes = expires_minutes

    def execute(self, username: str, password: str) -> str:
        """Return a signed access token, or raise InvalidCredentials."""
        user = self._repo.get_by_username(username)
        if user is None or not auth.verify_password(password, user.password_hash):
            raise InvalidCredentials
        assert user.id is not None
        return auth.create_access_token(user.id, user.role, self._jwt_secret, self._expires_minutes)
