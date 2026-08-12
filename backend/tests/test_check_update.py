from __future__ import annotations

import pytest
from application.check_update import CheckUpdate, CheckUpdateRequest, ModelNotFound
from conftest import FakeDeviceRepository, FakeFirmwareRepository
from domain.models import Firmware


def make_use_case(rows=(), devices=None) -> CheckUpdate:
    return CheckUpdate(
        FakeFirmwareRepository(rows),
        devices if devices is not None else FakeDeviceRepository(),
    )


def make_request(model="ESP32", version="1.0.0", **overrides) -> CheckUpdateRequest:
    return CheckUpdateRequest(model=model, version=version, **overrides)


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
        use_case.execute(make_request())


def test_execute_reports_no_update_when_current_version_is_latest():
    latest = make_firmware(version="1.0.0")
    use_case = make_use_case([latest])

    result = use_case.execute(make_request())

    assert result.update_available is False
    assert result.version is None
    assert result.download_url is None


def test_execute_reports_update_with_signature_and_download_url():
    latest = make_firmware(version="1.2.0", firmware_id=42)
    use_case = make_use_case([latest])

    result = use_case.execute(make_request(version="1.1.0"))

    assert result.update_available is True
    assert result.model == "ESP32"
    assert result.version == "1.2.0"
    assert result.signature == latest.signature
    assert result.download_url == "/api/download/42"


def test_execute_checks_the_requested_model_only():
    other_model_latest = make_firmware(model="ESP32-S3", version="9.9.9")
    use_case = make_use_case([other_model_latest])

    with pytest.raises(ModelNotFound):
        use_case.execute(make_request())


def test_execute_records_checkin_when_device_id_present():
    devices = FakeDeviceRepository()
    use_case = make_use_case([make_firmware(version="1.1.0")], devices)

    use_case.execute(make_request(device_id="aa:bb:cc"))

    recorded = devices.devices["aa:bb:cc"]
    assert recorded.model == "ESP32"
    assert recorded.current_version == "1.0.0"
    assert recorded.last_seen is not None


def test_execute_records_reported_telemetry():
    devices = FakeDeviceRepository()
    use_case = make_use_case([make_firmware(version="1.1.0")], devices)

    use_case.execute(
        make_request(device_id="aa:bb:cc", poll_interval_seconds=6, rssi=-52, ip="10.0.4.11")
    )

    recorded = devices.devices["aa:bb:cc"]
    assert recorded.poll_interval_seconds == 6
    assert recorded.rssi == -52
    assert recorded.ip == "10.0.4.11"


def test_execute_accepts_a_checkin_carrying_no_telemetry():
    """The route requires the telemetry; the use case never has.

    Keeping this end open is what lets the deployment question (what our one
    device must send) move without touching the update decision.
    """
    devices = FakeDeviceRepository()
    use_case = make_use_case([make_firmware(version="1.1.0")], devices)

    result = use_case.execute(make_request(device_id="aa:bb:cc"))

    assert result.update_available is True
    assert devices.devices["aa:bb:cc"].poll_interval_seconds is None


def test_execute_skips_recording_without_device_id():
    devices = FakeDeviceRepository()
    use_case = make_use_case([make_firmware(version="1.1.0")], devices)

    use_case.execute(make_request())

    assert devices.devices == {}


def test_execute_records_checkin_even_for_unknown_model():
    devices = FakeDeviceRepository()
    use_case = make_use_case([], devices)

    with pytest.raises(ModelNotFound):
        use_case.execute(make_request(device_id="aa:bb:cc"))

    assert "aa:bb:cc" in devices.devices
