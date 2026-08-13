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
from conftest import FakeUserRepository
from domain import auth
from domain.firmware_image import InvalidFirmwareImage
from domain.models import Firmware, Role, User
from domain.signing import InvalidManifestField
from fastapi.testclient import TestClient
from main import app
from ports.repository import FirmwareAlreadyExists, FirmwareBinaryAlreadyExists


def seed_user(repo: FakeUserRepository, username: str, password: str, role: Role) -> User:
    """Add an account with a real bcrypt hash, so login goes through the real check."""
    return repo.add(User(username=username, password_hash=auth.hash_password(password), role=role))


class FakeUploadFirmware:
    def execute(self, req) -> Firmware:
        return Firmware(
            model=req.model,
            version=req.version,
            filename="f.bin",
            signature="s",
            sha256="a" * 64,
            size_bytes=0,
        )


class RecordingUploadFirmware(FakeUploadFirmware):
    def __init__(self) -> None:
        self.req = None

    def execute(self, req) -> Firmware:
        self.req = req
        return super().execute(req)


class FakeUploadFirmwareTakenVersion:
    def execute(self, req) -> Firmware:
        raise FirmwareAlreadyExists(req.model, req.version)


class FakeUploadFirmwareBadImage:
    def execute(self, req) -> Firmware:
        raise InvalidFirmwareImage("Not an ESP32 image: expected magic 0xE9, found 0x62")


class FakeUploadFirmwareStoredBinary:
    def execute(self, req) -> Firmware:
        raise FirmwareBinaryAlreadyExists(req.model, "1.0.2")


class FakeUploadFirmwareBadVersion:
    def execute(self, req) -> Firmware:
        raise InvalidManifestField("version must look like 1.2.3, got 'v2.0.0'")


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
    # 400, not Pydantic's 422: what makes a credential acceptable is a domain
    # rule, so `scripts/create_user.py` is held to it through the same path.
    res = client.post("/api/auth/register", json={"username": "bob", "password": "short"})

    assert res.status_code == 400
    assert users.get_by_username("bob") is None


def test_register_rejects_empty_username(users, client):
    res = client.post("/api/auth/register", json={"username": "", "password": "long-enough"})

    assert res.status_code == 400
    assert users.get_by_username("") is None


def test_register_rejects_password_over_bcrypt_limit(users, client):
    res = client.post("/api/auth/register", json={"username": "bob", "password": "x" * 73})

    assert res.status_code == 400
    assert users.get_by_username("bob") is None


def test_login_rejects_overlong_password_as_401(users, client):
    # Must be a clean 401, not a 500 from bcrypt's 72-byte limit.
    seed_user(users, "bob", "s3cretpw", Role.OPERATOR)

    res = client.post("/api/auth/login", json={"username": "bob", "password": "x" * 73})

    assert res.status_code == 401


def test_register_rejects_duplicate_username(users, client):
    seed_user(users, "bob", "s3cretpw", Role.OPERATOR)

    res = client.post("/api/auth/register", json={"username": "bob", "password": "s3cretpw"})

    assert res.status_code == 409


def test_login_rejects_bad_password(users, client):
    seed_user(users, "bob", "pw", Role.OPERATOR)

    res = client.post("/api/auth/login", json={"username": "bob", "password": "nope"})

    assert res.status_code == 401


def test_login_returns_usable_token(users, client):
    seed_user(users, "bob", "pw", Role.OPERATOR)

    token = login(client, "bob", "pw")

    settings = get_settings()
    user_id, role = auth.decode_access_token(token, settings.jwt_secret)
    assert user_id == users.get_by_username("bob").id
    assert role is Role.OPERATOR


def test_upload_requires_a_token(users, client):
    res = client.post("/firmware/upload", files=upload_files())

    assert res.status_code == 401


def test_upload_forbidden_for_operator(users, client):
    seed_user(users, "op", "pw", Role.OPERATOR)
    token = login(client, "op", "pw")

    res = client.post(
        "/firmware/upload", files=upload_files(), headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 403


def test_upload_succeeds_for_admin(users, client):
    seed_user(users, "admin", "pw", Role.ADMIN)
    app.dependency_overrides[get_upload_firmware] = lambda: FakeUploadFirmware()
    token = login(client, "admin", "pw")

    res = client.post(
        "/firmware/upload", files=upload_files(), headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_upload_carries_notes_through_to_the_use_case(users, client):
    """The form field name is the whole contract here.

    Normalizing blank notes is the use case's job and tested there. What only
    the route can get wrong is the name Pydantic binds the field under, and a
    typo there silently drops every note the admin types.
    """
    seed_user(users, "admin", "pw", Role.ADMIN)
    use_case = RecordingUploadFirmware()
    app.dependency_overrides[get_upload_firmware] = lambda: use_case
    token = login(client, "admin", "pw")

    res = client.post(
        "/firmware/upload",
        files=upload_files() | {"notes": (None, "Fix SNTP retry storm")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 200
    assert use_case.req.notes == "Fix SNTP retry storm"


def test_upload_without_notes_reaches_the_use_case_as_none(users, client):
    seed_user(users, "admin", "pw", Role.ADMIN)
    use_case = RecordingUploadFirmware()
    app.dependency_overrides[get_upload_firmware] = lambda: use_case
    token = login(client, "admin", "pw")

    res = client.post(
        "/firmware/upload", files=upload_files(), headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
    assert use_case.req.notes is None


def test_upload_conflicts_on_a_version_already_stored(users, client):
    seed_user(users, "admin", "pw", Role.ADMIN)
    app.dependency_overrides[get_upload_firmware] = lambda: FakeUploadFirmwareTakenVersion()
    token = login(client, "admin", "pw")

    res = client.post(
        "/firmware/upload", files=upload_files(), headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 409


def test_upload_rejects_a_file_that_is_not_an_esp32_image(users, client):
    seed_user(users, "admin", "pw", Role.ADMIN)
    app.dependency_overrides[get_upload_firmware] = lambda: FakeUploadFirmwareBadImage()
    token = login(client, "admin", "pw")

    res = client.post(
        "/firmware/upload", files=upload_files(), headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 400
    # The route must pass the validator's message through, not flatten it.
    assert "0xE9" in res.json()["detail"]


def test_upload_rejects_a_version_the_manifest_cannot_carry(users, client):
    seed_user(users, "admin", "pw", Role.ADMIN)
    app.dependency_overrides[get_upload_firmware] = lambda: FakeUploadFirmwareBadVersion()
    token = login(client, "admin", "pw")

    res = client.post(
        "/firmware/upload", files=upload_files(), headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 400
    assert "1.2.3" in res.json()["detail"]


def test_upload_conflicts_on_a_binary_already_stored(users, client):
    seed_user(users, "admin", "pw", Role.ADMIN)
    app.dependency_overrides[get_upload_firmware] = lambda: FakeUploadFirmwareStoredBinary()
    token = login(client, "admin", "pw")

    res = client.post(
        "/firmware/upload", files=upload_files(), headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 409
    assert "1.0.2" in res.json()["detail"]
