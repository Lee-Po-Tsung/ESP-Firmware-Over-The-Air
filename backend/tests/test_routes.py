"""HTTP-level tests for the device protocol and read-only routes.

The admin gate on `/firmware/upload` is covered in `test_auth_routes.py`.
"""

from __future__ import annotations

import pytest
from api.deps import get_check_update, get_firmware_repository, get_storage
from application.check_update import CheckUpdate
from domain.models import Firmware
from fastapi.testclient import TestClient
from main import app


class FakeFirmwareRepository:
    def __init__(self, firmware_by_id=None, firmware_by_model=None, all_firmware=None) -> None:
        self._firmware_by_id = firmware_by_id or {}
        self._firmware_by_model = firmware_by_model or {}
        self._all_firmware = all_firmware or []

    def add(self, firmware: Firmware) -> Firmware:
        raise NotImplementedError

    def get_by_id(self, firmware_id: int) -> Firmware | None:
        return self._firmware_by_id.get(firmware_id)

    def get_latest_for_model(self, model: str) -> Firmware | None:
        return self._firmware_by_model.get(model)

    def list_all(self) -> list[Firmware]:
        return self._all_firmware


class FakeStorage:
    def __init__(self, files: dict[str, bytes] | None = None) -> None:
        self.files = files or {}

    def put(self, filename: str, data: bytes) -> None:
        self.files[filename] = data

    def get(self, filename: str) -> bytes:
        return self.files[filename]

    def delete(self, filename: str) -> None:
        self.files.pop(filename, None)

    def exists(self, filename: str) -> bool:
        return filename in self.files


def make_firmware(model="ESP32", version="1.0.0", firmware_id=1) -> Firmware:
    return Firmware(
        model=model,
        version=version,
        filename=f"{firmware_id}_firmware.bin",
        signature="c2ln",
        sha256="a" * 64,
        id=firmware_id,
    )


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_check_update_returns_403_for_unknown_model(client):
    app.dependency_overrides[get_check_update] = lambda: CheckUpdate(FakeFirmwareRepository())

    response = client.post("/api/check", json={"model": "ESP32", "version": "1.0.0"})

    assert response.status_code == 403


def test_check_update_reports_no_update_when_current_is_latest(client):
    latest = make_firmware(version="1.0.0")
    app.dependency_overrides[get_check_update] = lambda: CheckUpdate(
        FakeFirmwareRepository(firmware_by_model={"ESP32": latest})
    )

    response = client.post("/api/check", json={"model": "ESP32", "version": "1.0.0"})

    assert response.status_code == 200
    assert response.json() == {"update_available": False}


def test_check_update_reports_available_update_with_download_url(client):
    latest = make_firmware(version="1.2.0", firmware_id=42)
    app.dependency_overrides[get_check_update] = lambda: CheckUpdate(
        FakeFirmwareRepository(firmware_by_model={"ESP32": latest})
    )

    response = client.post(
        "/api/check", json={"model": "ESP32", "version": "1.1.0", "device_id": "dev-1"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "update_available": True,
        "version": "1.2.0",
        "signature": "c2ln",
        "download_url": "/api/download/42",
    }


def test_download_firmware_returns_404_for_unknown_id(client):
    app.dependency_overrides[get_firmware_repository] = lambda: FakeFirmwareRepository()
    app.dependency_overrides[get_storage] = lambda: FakeStorage()

    response = client.get("/api/download/999")

    assert response.status_code == 404


def test_download_firmware_returns_404_when_file_missing_from_storage(client):
    firmware = make_firmware(firmware_id=1)
    app.dependency_overrides[get_firmware_repository] = lambda: FakeFirmwareRepository(
        firmware_by_id={1: firmware}
    )
    app.dependency_overrides[get_storage] = lambda: FakeStorage()  # file was never stored

    response = client.get("/api/download/1")

    assert response.status_code == 404


def test_download_firmware_returns_binary_with_expected_headers(client):
    firmware = make_firmware(firmware_id=1)
    app.dependency_overrides[get_firmware_repository] = lambda: FakeFirmwareRepository(
        firmware_by_id={1: firmware}
    )
    app.dependency_overrides[get_storage] = lambda: FakeStorage(
        {firmware.filename: b"binary contents"}
    )

    response = client.get("/api/download/1")

    assert response.status_code == 200
    assert response.content == b"binary contents"
    assert response.headers["content-type"] == "application/octet-stream"
    assert firmware.filename in response.headers["content-disposition"]


def test_firmware_list_api_returns_all_firmware_as_json(client):
    firmware = make_firmware(firmware_id=1)
    app.dependency_overrides[get_firmware_repository] = lambda: FakeFirmwareRepository(
        all_firmware=[firmware]
    )

    response = client.get("/api/firmware/list")

    assert response.status_code == 200
    assert response.json()[0]["model"] == "ESP32"
    assert response.json()[0]["id"] == 1
