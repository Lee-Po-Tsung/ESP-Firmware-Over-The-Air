"""HTTP-level tests for the auth flow and the admin gate on firmware upload.

Registers and logs in through the real endpoints, then uses the returned JWT to
prove the role gate: no token is 401, an operator is 403, an admin succeeds.
"""

from __future__ import annotations

import io

import pytest
from api.deps import get_authenticate_user, get_upload_firmware, get_user_repository
from application.auth import AuthenticateUser
from config import get_settings
from domain import auth
from domain.models import Firmware, Role, User
from fastapi.testclient import TestClient
from main import app
from ports.repository import UserAlreadyExists


class FakeUserRepository:
    def __init__(self) -> None:
        self._by_id: dict[int, User] = {}
        self._by_name: dict[str, User] = {}

    def add(self, user: User) -> User:
        if user.username in self._by_name:
            raise UserAlreadyExists(user.username)
        user.id = len(self._by_id) + 1
        self._by_id[user.id] = user
        self._by_name[user.username] = user
        return user

    def get_by_id(self, user_id: int) -> User | None:
        return self._by_id.get(user_id)

    def get_by_username(self, username: str) -> User | None:
        return self._by_name.get(username)

    def seed(self, username: str, password: str, role: Role) -> User:
        return self.add(
            User(username=username, password_hash=auth.hash_password(password), role=role)
        )


class FakeUploadFirmware:
    def execute(self, req) -> Firmware:
        return Firmware(
            model=req.model, version=req.version, filename="f.bin", signature="s", sha256="a" * 64
        )


@pytest.fixture
def users():
    repo = FakeUserRepository()
    app.dependency_overrides[get_user_repository] = lambda: repo
    settings = get_settings()
    app.dependency_overrides[get_authenticate_user] = lambda: AuthenticateUser(
        repo, settings.jwt_secret, settings.jwt_expires_minutes
    )
    yield repo
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def login(client, username, password) -> str:
    res = client.post("/api/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def upload_files():
    return {
        "model": (None, "ESP32"),
        "version": (None, "1.0.0"),
        "firmware": ("f.bin", io.BytesIO(b"binary"), "application/octet-stream"),
    }


def test_register_creates_operator(users, client):
    res = client.post("/api/auth/register", json={"username": "bob", "password": "s3cretpw"})

    assert res.status_code == 201
    assert res.json()["role"] == "operator"
    assert users.get_by_username("bob") is not None


def test_register_rejects_short_password(users, client):
    res = client.post("/api/auth/register", json={"username": "bob", "password": "short"})

    assert res.status_code == 422
    assert users.get_by_username("bob") is None


def test_register_rejects_password_over_bcrypt_limit(users, client):
    res = client.post("/api/auth/register", json={"username": "bob", "password": "x" * 73})

    assert res.status_code == 422
    assert users.get_by_username("bob") is None


def test_login_rejects_overlong_password_as_401(users, client):
    # Must be a clean 401, not a 500 from bcrypt's 72-byte limit.
    users.seed("bob", "s3cretpw", Role.OPERATOR)

    res = client.post("/api/auth/login", json={"username": "bob", "password": "x" * 73})

    assert res.status_code == 401


def test_register_rejects_duplicate_username(users, client):
    users.seed("bob", "s3cretpw", Role.OPERATOR)

    res = client.post("/api/auth/register", json={"username": "bob", "password": "s3cretpw"})

    assert res.status_code == 409


def test_login_rejects_bad_password(users, client):
    users.seed("bob", "pw", Role.OPERATOR)

    res = client.post("/api/auth/login", json={"username": "bob", "password": "nope"})

    assert res.status_code == 401


def test_login_returns_usable_token(users, client):
    users.seed("bob", "pw", Role.OPERATOR)

    token = login(client, "bob", "pw")

    settings = get_settings()
    user_id, role = auth.decode_access_token(token, settings.jwt_secret)
    assert user_id == users.get_by_username("bob").id
    assert role is Role.OPERATOR


def test_upload_requires_a_token(users, client):
    res = client.post("/firmware/upload", files=upload_files())

    assert res.status_code == 401


def test_upload_forbidden_for_operator(users, client):
    users.seed("op", "pw", Role.OPERATOR)
    token = login(client, "op", "pw")

    res = client.post(
        "/firmware/upload", files=upload_files(), headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 403


def test_upload_succeeds_for_admin(users, client):
    users.seed("admin", "pw", Role.ADMIN)
    app.dependency_overrides[get_upload_firmware] = lambda: FakeUploadFirmware()
    token = login(client, "admin", "pw")

    res = client.post(
        "/firmware/upload", files=upload_files(), headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
