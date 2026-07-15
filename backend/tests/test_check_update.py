from __future__ import annotations

import pytest
from application.check_update import CheckUpdate, ModelNotFound
from domain.models import Device, Firmware


class FakeFirmwareRepository:
    """In-memory stand-in for `FirmwareRepository`, keyed by model."""

    def __init__(self, firmware_by_model: dict[str, Firmware]) -> None:
        self._firmware_by_model = firmware_by_model

    def add(self, firmware: Firmware) -> Firmware:
        raise NotImplementedError

    def get_by_id(self, firmware_id: int) -> Firmware | None:
        raise NotImplementedError

    def get_latest_for_model(self, model: str) -> Firmware | None:
        return self._firmware_by_model.get(model)

    def list_all(self) -> list[Firmware]:
        raise NotImplementedError


class FakeDeviceRepository:
    """In-memory stand-in for `DeviceRepository`, keyed by device id."""

    def __init__(self) -> None:
        self.devices: dict[str, Device] = {}

    def get_by_device_id(self, device_id: str) -> Device | None:
        return self.devices.get(device_id)

    def upsert(self, device: Device) -> Device:
        self.devices[device.device_id] = device
        return device


def make_use_case(firmware_by_model=None, devices=None) -> CheckUpdate:
    return CheckUpdate(
        FakeFirmwareRepository(firmware_by_model or {}),
        devices if devices is not None else FakeDeviceRepository(),
    )


def make_firmware(model="ESP32", version="1.1.0", firmware_id=7) -> Firmware:
    return Firmware(
        model=model,
        version=version,
        filename=f"{firmware_id}_firmware.bin",
        signature="c2ln",
        sha256="a" * 64,
        id=firmware_id,
    )


def test_execute_raises_when_model_unknown():
    use_case = make_use_case()

    with pytest.raises(ModelNotFound):
        use_case.execute("ESP32", "1.0.0")


def test_execute_reports_no_update_when_current_version_is_latest():
    latest = make_firmware(version="1.0.0")
    use_case = make_use_case({"ESP32": latest})

    result = use_case.execute("ESP32", "1.0.0")

    assert result.update_available is False
    assert result.version is None
    assert result.download_url is None


def test_execute_reports_update_with_signature_and_download_url():
    latest = make_firmware(version="1.2.0", firmware_id=42)
    use_case = make_use_case({"ESP32": latest})

    result = use_case.execute("ESP32", "1.1.0")

    assert result.update_available is True
    assert result.model == "ESP32"
    assert result.version == "1.2.0"
    assert result.signature == latest.signature
    assert result.download_url == "/api/download/42"


def test_execute_checks_the_requested_model_only():
    other_model_latest = make_firmware(model="ESP32-S3", version="9.9.9")
    use_case = make_use_case({"ESP32-S3": other_model_latest})

    with pytest.raises(ModelNotFound):
        use_case.execute("ESP32", "1.0.0")


def test_execute_records_checkin_when_device_id_present():
    devices = FakeDeviceRepository()
    use_case = make_use_case({"ESP32": make_firmware(version="1.1.0")}, devices)

    use_case.execute("ESP32", "1.0.0", device_id="aa:bb:cc")

    recorded = devices.devices["aa:bb:cc"]
    assert recorded.model == "ESP32"
    assert recorded.current_version == "1.0.0"
    assert recorded.last_seen is not None


def test_execute_skips_recording_without_device_id():
    devices = FakeDeviceRepository()
    use_case = make_use_case({"ESP32": make_firmware(version="1.1.0")}, devices)

    use_case.execute("ESP32", "1.0.0")

    assert devices.devices == {}


def test_execute_records_checkin_even_for_unknown_model():
    devices = FakeDeviceRepository()
    use_case = make_use_case({}, devices)

    with pytest.raises(ModelNotFound):
        use_case.execute("ESP32", "1.0.0", device_id="aa:bb:cc")

    assert "aa:bb:cc" in devices.devices
