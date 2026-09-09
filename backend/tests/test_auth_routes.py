"""HTTP-level tests for the auth flow and the admin gate on firmware upload.

Registers and logs in through the real endpoints, then uses the returned JWT to
prove the role gate: no token is 401, an operator is 403, an admin succeeds.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone

import pytest
from api.deps import (
    get_authenticate_user,
    get_firmware_repository,
    get_upload_firmware,
    get_user_repository,
)
from api.routes import MULTIPART_OVERHEAD_ALLOWANCE
from application.auth import AuthenticateUser
from application.upload_firmware import InvalidUploadIdentity
from config import get_settings
from conftest import FakeFirmwareRepository, FakeUserRepository
from domain import auth
from domain.firmware_image import MAX_FIRMWARE_BYTES, InvalidFirmwareImage
from domain.models import Firmware, Role, User
from domain.signing import InvalidManifestField
from fastapi.testclient import TestClient
from main import app
from ports.repository import FirmwareAlreadyExists, FirmwareBinaryAlreadyExists


def seed_user(repo: FakeUserRepository, username: str, password: str, role: Role) -> User:
    """Add an account with a real bcrypt hash, so login goes through the real check."""
    return repo.add(User(username=username, password_hash=auth.hash_password(password), role=role))


def make_firmware(firmware_id=1) -> Firmware:
    return Firmware(
        model="ESP32",
        version="1.0.0",
        filename="f.bin",
        original_filename="f.bin",
        signature="s",
        sha256="a" * 64,
        size_bytes=1,
        id=firmware_id,
        created_at=datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc),
    )


class FakeUploadFirmware:
    def execute(self, req) -> Firmware:
        # The real use case reads these out of the image whenever the form
        # leaves them out, so stand in for that rather than handing None back
        # to a response model that promises strings.
        return Firmware(
            model=req.model or "ESP32",
            version=req.version or "1.0.0",
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


class FakeUploadFirmwareContradicted:
    def execute(self, req) -> Firmware:
        raise InvalidUploadIdentity("Image says ESP32 1.0.5, upload says ESP32 1.0.4")


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


def test_no_registration_route_exists(users, client):
    # What makes a credential acceptable is covered at the domain layer in
    # test_auth.py, which is the path `scripts/create_user.py` takes.
    res = client.post("/api/auth/register", json={"username": "bob", "password": "s3cretpw"})

    assert res.status_code == 404
    assert users.get_by_username("bob") is None


def test_login_rejects_overlong_password_as_401(users, client):
    # Must be a clean 401, not a 500 from bcrypt's 72-byte limit.
    seed_user(users, "bob", "s3cretpw", Role.OPERATOR)

    res = client.post("/api/auth/login", json={"username": "bob", "password": "x" * 73})

    assert res.status_code == 401


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
    # The identity rides back on the response because the uploader need not have
    # typed it: an image carrying a build marker names itself.
    assert res.json() == {"status": "ok", "model": "ESP32", "version": "1.0.0"}


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


def test_upload_reports_a_label_the_image_contradicts(users, client):
    """Both values reach the admin, since only they can tell which one is wrong."""
    seed_user(users, "admin", "pw", Role.ADMIN)
    app.dependency_overrides[get_upload_firmware] = lambda: FakeUploadFirmwareContradicted()
    token = login(client, "admin", "pw")

    res = client.post(
        "/firmware/upload", files=upload_files(), headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 400
    assert "1.0.5" in res.json()["detail"]
    assert "1.0.4" in res.json()["detail"]


def test_upload_without_a_typed_model_or_version_is_accepted(users, client):
    """The normal path once an image names itself: the form sends neither field."""
    seed_user(users, "admin", "pw", Role.ADMIN)
    recorder = RecordingUploadFirmware()
    app.dependency_overrides[get_upload_firmware] = lambda: recorder
    token = login(client, "admin", "pw")

    res = client.post(
        "/firmware/upload",
        files={"firmware": ("f.bin", io.BytesIO(b"binary"), "application/octet-stream")},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.status_code == 200
    assert recorder.req.model is None
    assert recorder.req.version is None


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


def test_deactivate_requires_a_token(client):
    res = client.post("/api/firmware/1/deactivate")

    assert res.status_code == 401


def test_deactivate_forbidden_for_operator(users, client):
    seed_user(users, "op", "pw", Role.OPERATOR)
    token = login(client, "op", "pw")

    res = client.post("/api/firmware/1/deactivate", headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 403


def test_deactivate_clears_active_for_admin(users, client):
    seed_user(users, "admin", "pw", Role.ADMIN)
    app.dependency_overrides[get_firmware_repository] = lambda: FakeFirmwareRepository(
        [make_firmware()]
    )
    token = login(client, "admin", "pw")

    res = client.post("/api/firmware/1/deactivate", headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 200
    assert res.json()["active"] is False


def test_deactivate_is_idempotent(users, client):
    seed_user(users, "admin", "pw", Role.ADMIN)
    app.dependency_overrides[get_firmware_repository] = lambda: FakeFirmwareRepository(
        [make_firmware()]
    )
    token = login(client, "admin", "pw")
    headers = {"Authorization": f"Bearer {token}"}

    first = client.post("/api/firmware/1/deactivate", headers=headers)
    second = client.post("/api/firmware/1/deactivate", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["active"] is False


def test_deactivate_returns_404_for_unknown_id(users, client):
    seed_user(users, "admin", "pw", Role.ADMIN)
    app.dependency_overrides[get_firmware_repository] = lambda: FakeFirmwareRepository()
    token = login(client, "admin", "pw")

    res = client.post("/api/firmware/999/deactivate", headers={"Authorization": f"Bearer {token}"})

    assert res.status_code == 404


def test_upload_rejects_a_body_past_the_ceiling(users, client):
    """413, not 400. Too small means "not an image"; too large means "too large"."""
    seed_user(users, "admin", "pw", Role.ADMIN)
    use_case = RecordingUploadFirmware()
    app.dependency_overrides[get_upload_firmware] = lambda: use_case
    token = login(client, "admin", "pw")

    oversized = upload_files() | {
        "firmware": (
            "f.bin",
            io.BytesIO(b"\xe9" * (MAX_FIRMWARE_BYTES + 1)),
            "application/octet-stream",
        )
    }
    res = client.post(
        "/firmware/upload", files=oversized, headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 413
    # Nothing was signed, stored or written: the use case never ran.
    assert use_case.req is None


def test_upload_accepts_a_body_at_the_ceiling(users, client):
    """An off-by-one here rejects a legitimate build with no way to tell why."""
    seed_user(users, "admin", "pw", Role.ADMIN)
    use_case = RecordingUploadFirmware()
    app.dependency_overrides[get_upload_firmware] = lambda: use_case
    token = login(client, "admin", "pw")

    at_limit = upload_files() | {
        "firmware": (
            "f.bin",
            io.BytesIO(b"\xe9" * MAX_FIRMWARE_BYTES),
            "application/octet-stream",
        )
    }
    res = client.post(
        "/firmware/upload", files=at_limit, headers={"Authorization": f"Bearer {token}"}
    )

    assert res.status_code == 200
    assert len(use_case.req.data) == MAX_FIRMWARE_BYTES


def test_upload_rejects_an_oversized_declared_body_before_reading_it(users, client):
    """The header check is the only one that can answer without reading the file."""
    seed_user(users, "admin", "pw", Role.ADMIN)
    use_case = RecordingUploadFirmware()
    app.dependency_overrides[get_upload_firmware] = lambda: use_case
    token = login(client, "admin", "pw")

    res = client.post(
        "/firmware/upload",
        files=upload_files(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Length": str(MAX_FIRMWARE_BYTES + MULTIPART_OVERHEAD_ALLOWANCE + 1),
        },
    )

    assert res.status_code == 413
    assert use_case.req is None


def test_upload_that_understates_its_length_is_still_capped(users, client):
    """The declared length is written by the client, so it cannot be the rule.

    The allowance the header check carries for multipart overhead makes this
    reachable in the other direction too: a body inside that slack passes the
    fast path and is stopped by the read.
    """
    seed_user(users, "admin", "pw", Role.ADMIN)
    use_case = RecordingUploadFirmware()
    app.dependency_overrides[get_upload_firmware] = lambda: use_case
    token = login(client, "admin", "pw")

    oversized = upload_files() | {
        "firmware": (
            "f.bin",
            io.BytesIO(b"\xe9" * (MAX_FIRMWARE_BYTES + 1)),
            "application/octet-stream",
        )
    }
    res = client.post(
        "/firmware/upload",
        files=oversized,
        headers={"Authorization": f"Bearer {token}", "Content-Length": "10"},
    )

    assert res.status_code == 413
    assert use_case.req is None
