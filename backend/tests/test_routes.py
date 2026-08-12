"""HTTP-level tests for the device protocol and read-only routes.

The admin gate on `/firmware/upload` is covered in `test_auth_routes.py`.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from api.deps import (
    get_check_update,
    get_current_user,
    get_device_repository,
    get_firmware_repository,
    get_storage,
)
from application.check_update import CheckUpdate
from conftest import FakeDeviceRepository, FakeFirmwareRepository, FakeStorage
from domain.models import Device, Firmware, Role, User
from fastapi.testclient import TestClient
from main import app


def make_operator() -> User:
    return User(username="op", password_hash="x", role=Role.OPERATOR, id=1)


def make_firmware(
    model="ESP32", version="1.0.0", firmware_id=1, original_filename="main.ino.bin"
) -> Firmware:
    return Firmware(
        model=model,
        version=version,
        filename=f"{firmware_id}_firmware.bin",
        original_filename=original_filename,
        signature="c2ln",
        sha256="a" * 64,
        id=firmware_id,
        # `id` and `created_at` are only ever None before the row is written,
        # and every route reads rows that already are.
        created_at=datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc),
    )


def check_payload(**overrides) -> dict:
    """A well-formed check-in. `ota.cpp` always sends the telemetry, so tests do too."""
    return {
        "model": "ESP32",
        "version": "1.0.0",
        "poll_interval_seconds": 6,
        "rssi": -52,
        "ip": "10.0.4.11",
    } | overrides


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_check_update_returns_403_for_unknown_model(client):
    app.dependency_overrides[get_check_update] = lambda: CheckUpdate(
        FakeFirmwareRepository(), FakeDeviceRepository()
    )

    response = client.post("/api/check", json=check_payload())

    assert response.status_code == 403


def test_check_update_reports_no_update_when_current_is_latest(client):
    latest = make_firmware(version="1.0.0")
    app.dependency_overrides[get_check_update] = lambda: CheckUpdate(
        FakeFirmwareRepository([latest]), FakeDeviceRepository()
    )

    response = client.post("/api/check", json=check_payload())

    assert response.status_code == 200
    assert response.json() == {"update_available": False}


def test_check_update_reports_available_update_with_download_url(client):
    latest = make_firmware(version="1.2.0", firmware_id=42)
    app.dependency_overrides[get_check_update] = lambda: CheckUpdate(
        FakeFirmwareRepository([latest]), FakeDeviceRepository()
    )

    response = client.post("/api/check", json=check_payload(version="1.1.0", device_id="dev-1"))

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "update_available": True,
        "version": "1.2.0",
        "signature": "c2ln",
        "download_url": "/api/download/42",
    }


def test_check_response_carries_only_what_the_device_reads(client):
    """`CheckUpdateResult` also holds `model`, which was never on the wire.

    The response model is what keeps that true: a field added to the use case's
    result no longer reaches a device by default.
    """
    latest = make_firmware(version="1.2.0", firmware_id=42)
    app.dependency_overrides[get_check_update] = lambda: CheckUpdate(
        FakeFirmwareRepository([latest]), FakeDeviceRepository()
    )

    body = client.post("/api/check", json=check_payload(version="1.1.0")).json()

    assert set(body) == {"update_available", "version", "signature", "download_url"}


def test_check_update_records_device_checkin(client):
    latest = make_firmware(version="1.2.0", firmware_id=42)
    devices = FakeDeviceRepository()
    app.dependency_overrides[get_check_update] = lambda: CheckUpdate(
        FakeFirmwareRepository([latest]), devices
    )

    client.post("/api/check", json=check_payload(version="1.1.0", device_id="dev-1"))

    assert devices.devices["dev-1"].current_version == "1.1.0"


def test_download_firmware_returns_404_for_unknown_id(client):
    app.dependency_overrides[get_firmware_repository] = lambda: FakeFirmwareRepository()
    app.dependency_overrides[get_storage] = lambda: FakeStorage()

    response = client.get("/api/download/999")

    assert response.status_code == 404


def test_download_firmware_returns_404_when_file_missing_from_storage(client):
    firmware = make_firmware(firmware_id=1)
    app.dependency_overrides[get_firmware_repository] = lambda: FakeFirmwareRepository([firmware])
    app.dependency_overrides[get_storage] = lambda: FakeStorage()  # file was never stored

    response = client.get("/api/download/1")

    assert response.status_code == 404


def test_download_firmware_returns_binary_with_expected_headers(client):
    firmware = make_firmware(firmware_id=1)
    app.dependency_overrides[get_firmware_repository] = lambda: FakeFirmwareRepository([firmware])
    app.dependency_overrides[get_storage] = lambda: FakeStorage(
        {firmware.filename: b"binary contents"}
    )

    response = client.get("/api/download/1")

    assert response.status_code == 200
    assert response.content == b"binary contents"
    assert response.headers["content-type"] == "application/octet-stream"
    # The blob is addressed by hash; the browser is offered the uploader's name.
    assert firmware.original_filename in response.headers["content-disposition"]


@pytest.mark.parametrize(
    "original_filename",
    ["韌體v1.bin", 'we"ird.bin', "line\nbreak.bin"],
    ids=["non-ascii", "quote", "control-char"],
)
def test_download_firmware_survives_a_hostile_upload_name(client, original_filename):
    """Header values are latin-1 encoded, so an unescaped name is a 500, not a cosmetic bug.

    A row that cannot be downloaded is worse than it sounds: `/api/check` keeps
    naming it as latest, so every device of that model retries forever.
    """
    firmware = make_firmware(firmware_id=1, original_filename=original_filename)
    app.dependency_overrides[get_firmware_repository] = lambda: FakeFirmwareRepository([firmware])
    app.dependency_overrides[get_storage] = lambda: FakeStorage(
        {firmware.filename: b"binary contents"}
    )

    response = client.get("/api/download/1")

    assert response.status_code == 200
    assert response.content == b"binary contents"
    disposition = response.headers["content-disposition"]
    assert disposition.startswith('attachment; filename="')
    # The fallback carries no character that could end the quoted string early
    # or split the header; the UTF-8 form keeps the real name recoverable.
    fallback = disposition.split('"')[1]
    assert fallback.isascii() and fallback.isprintable()
    assert "filename*=UTF-8''" in disposition


def test_firmware_list_requires_login(client):
    response = client.get("/api/firmware/list")

    assert response.status_code == 401


def test_firmware_list_api_returns_all_firmware_as_json(client):
    firmware = make_firmware(firmware_id=1)
    app.dependency_overrides[get_firmware_repository] = lambda: FakeFirmwareRepository([firmware])
    app.dependency_overrides[get_current_user] = lambda: make_operator()

    response = client.get("/api/firmware/list")

    assert response.status_code == 200
    assert response.json()[0]["model"] == "ESP32"
    assert response.json()[0]["id"] == 1


def test_firmware_list_created_at_carries_a_utc_offset(client):
    """The two list routes used to disagree, and only one of them was right.

    An ISO string with no offset is read as local time by a browser, so a
    dashboard showed upload times shifted while device times beside them were
    correct.
    """
    firmware = make_firmware(firmware_id=1)
    app.dependency_overrides[get_firmware_repository] = lambda: FakeFirmwareRepository([firmware])
    app.dependency_overrides[get_current_user] = lambda: make_operator()

    response = client.get("/api/firmware/list")

    assert response.json()[0]["created_at"] == "2026-07-15T12:00:00Z"


def test_device_list_derives_online_from_the_reported_interval(client):
    """`online` is the one key with no column behind it.

    It is answered against the clock at request time, so a device that checked
    in moments ago reads as online without anything having written a status.
    """
    devices = FakeDeviceRepository()
    devices.upsert(
        Device(
            id=1,
            device_id="aa:bb:cc",
            model="ESP32",
            current_version="1.0.0",
            last_seen=datetime.now(timezone.utc),
            poll_interval_seconds=6,
            rssi=-52,
            ip="10.0.4.11",
        )
    )
    app.dependency_overrides[get_device_repository] = lambda: devices
    app.dependency_overrides[get_current_user] = lambda: make_operator()

    body = client.get("/api/devices").json()

    assert body[0]["online"] is True
    assert body[0]["rssi"] == -52
    assert body[0]["ip"] == "10.0.4.11"
    assert body[0]["poll_interval_seconds"] == 6


def test_device_list_requires_login(client):
    response = client.get("/api/devices")

    assert response.status_code == 401


def test_device_list_returns_devices_with_utc_last_seen(client):
    # The repository is what re-attaches the offset SQLite drops, so a fake
    # standing in for it hands back an aware datetime too.
    devices = FakeDeviceRepository()
    devices.upsert(
        Device(
            id=1,
            device_id="aa:bb:cc",
            model="ESP32",
            current_version="1.0.0",
            last_seen=datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc),
        )
    )
    app.dependency_overrides[get_device_repository] = lambda: devices
    app.dependency_overrides[get_current_user] = lambda: make_operator()

    response = client.get("/api/devices")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 1,
            "device_id": "aa:bb:cc",
            "model": "ESP32",
            "current_version": "1.0.0",
            # FastAPI's encoder writes UTC as `Z`, where the hand-rolled
            # `isoformat()` this replaced wrote `+00:00`. Both parse the same.
            "last_seen": "2026-07-15T12:00:00Z",
            # A device on firmware from before it reported these. `online` is
            # null rather than false: nothing here says the device is gone.
            "poll_interval_seconds": None,
            "rssi": None,
            "ip": None,
            "online": None,
        }
    ]
