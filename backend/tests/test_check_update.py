from __future__ import annotations

import pytest
from application.check_update import CheckUpdate, CheckUpdateRequest, ModelNotFound
from conftest import FakeDeviceEventRepository, FakeDeviceRepository, FakeFirmwareRepository
from domain.models import DeviceEvent, EventType, Firmware


def make_use_case(rows=(), devices=None, events=None) -> CheckUpdate:
    return CheckUpdate(
        FakeFirmwareRepository(rows),
        devices if devices is not None else FakeDeviceRepository(),
        events if events is not None else FakeDeviceEventRepository(),
    )


def make_request(model="ESP32", version="1.0.0", **overrides) -> CheckUpdateRequest:
    return CheckUpdateRequest(model=model, version=version, **overrides)


def make_firmware(model="ESP32", version="1.1.0", firmware_id=7, active=True) -> Firmware:
    return Firmware(
        model=model,
        version=version,
        filename=f"{firmware_id}_firmware.bin",
        signature="c2ln",
        sha256="a" * 64,
        size_bytes=1,
        id=firmware_id,
        active=active,
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


def test_execute_reports_no_update_when_latest_version_is_deactivated():
    """A withdrawn 1.0.1 must not be offered, but the model still exists.

    `get_latest_for_model` falls back to the newest active row, so the device
    on 1.0.0 gets a plain no-update, not a 403 and not a download.
    """
    older = make_firmware(version="1.0.0", firmware_id=1)
    withdrawn = make_firmware(version="1.0.1", firmware_id=2, active=False)
    use_case = make_use_case([older, withdrawn])

    result = use_case.execute(make_request(version="1.0.0"))

    assert result.update_available is False
    assert result.version is None
    assert result.download_url is None


def test_execute_raises_when_every_version_is_inactive():
    use_case = make_use_case(
        [
            make_firmware(version="1.0.0", firmware_id=1, active=False),
            make_firmware(version="1.0.1", firmware_id=2, active=False),
        ]
    )

    with pytest.raises(ModelNotFound):
        use_case.execute(make_request())


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


def test_a_device_moving_up_a_version_records_a_success():
    devices = FakeDeviceRepository()
    events = FakeDeviceEventRepository()
    use_case = make_use_case([make_firmware(version="1.2.0")], devices, events)

    use_case.execute(make_request(version="1.0.0", device_id="dev-1"))
    use_case.execute(make_request(version="1.2.0", device_id="dev-1"))

    success = next(e for e in events.events if e.event_type is EventType.SUCCESS)
    assert (success.from_version, success.to_version) == ("1.0.0", "1.2.0")


def test_a_device_coming_back_on_an_older_version_records_a_rollback():
    """The device rolled itself back, so the server only ever sees the result.

    Nothing in the protocol reports a failed flash after the reboot; the
    version going backwards between two check-ins is the whole signal.
    """
    devices = FakeDeviceRepository()
    events = FakeDeviceEventRepository()
    use_case = make_use_case([make_firmware(version="1.2.0")], devices, events)

    use_case.execute(make_request(version="1.1.0", device_id="dev-1"))
    use_case.execute(make_request(version="1.0.0", device_id="dev-1"))

    rollback = next(e for e in events.events if e.event_type is EventType.ROLLBACK)
    assert (rollback.from_version, rollback.to_version) == ("1.1.0", "1.0.0")


def test_a_check_event_is_recorded_only_when_an_update_is_offered():
    """Devices poll every few seconds. A row per check-in is tens of thousands
    a day per device, all repeating what `last_seen` already says."""
    devices = FakeDeviceRepository()
    events = FakeDeviceEventRepository()
    use_case = make_use_case([make_firmware(version="1.0.0")], devices, events)

    use_case.execute(make_request(version="1.0.0", device_id="dev-1"))
    use_case.execute(make_request(version="1.0.0", device_id="dev-1"))

    assert events.types() == []


def test_a_standing_offer_is_recorded_once_not_once_per_poll():
    """The same offer stands until the device acts on it, and it polls every
    few seconds. Recording each one is the volume this table cannot carry."""
    events = FakeDeviceEventRepository()
    use_case = make_use_case([make_firmware(version="1.2.0")], FakeDeviceRepository(), events)

    for _ in range(5):
        use_case.execute(make_request(version="1.0.0", device_id="dev-1"))

    assert events.types() == [EventType.CHECK]


def test_an_offer_after_the_device_did_something_is_recorded_again():
    """A download in between means the offer that follows it is a new one."""
    events = FakeDeviceEventRepository()
    use_case = make_use_case([make_firmware(version="1.2.0")], FakeDeviceRepository(), events)

    use_case.execute(make_request(version="1.0.0", device_id="dev-1"))
    events.add(DeviceEvent(device_id="dev-1", event_type=EventType.DOWNLOAD, to_version="1.2.0"))
    use_case.execute(make_request(version="1.0.0", device_id="dev-1"))

    assert events.types() == [EventType.CHECK, EventType.DOWNLOAD, EventType.CHECK]


def test_an_offer_records_a_check_naming_both_versions():
    devices = FakeDeviceRepository()
    events = FakeDeviceEventRepository()
    use_case = make_use_case([make_firmware(version="1.2.0")], devices, events)

    use_case.execute(make_request(version="1.0.0", device_id="dev-1"))

    assert events.types() == [EventType.CHECK]
    assert (events.events[0].from_version, events.events[0].to_version) == ("1.0.0", "1.2.0")


def test_a_checkin_without_a_device_id_records_nothing():
    events = FakeDeviceEventRepository()
    use_case = make_use_case([make_firmware(version="1.2.0")], FakeDeviceRepository(), events)

    use_case.execute(make_request(version="1.0.0"))

    assert events.types() == []


def test_the_download_url_carries_the_reported_device_id():
    use_case = make_use_case([make_firmware(version="1.2.0", firmware_id=7)])

    result = use_case.execute(make_request(version="1.0.0", device_id="aa:bb:cc"))

    assert result.download_url == "/api/download/7?device_id=aa%3Abb%3Acc"


def test_the_download_url_is_unchanged_when_no_device_id_was_reported():
    use_case = make_use_case([make_firmware(version="1.2.0", firmware_id=7)])

    result = use_case.execute(make_request(version="1.0.0"))

    assert result.download_url == "/api/download/7"
