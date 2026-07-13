from __future__ import annotations

import pytest
from application.check_update import CheckUpdate, ModelNotFound
from domain.models import Firmware


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
    use_case = CheckUpdate(FakeFirmwareRepository({}))

    with pytest.raises(ModelNotFound):
        use_case.execute("ESP32", "1.0.0")


def test_execute_reports_no_update_when_current_version_is_latest():
    latest = make_firmware(version="1.0.0")
    use_case = CheckUpdate(FakeFirmwareRepository({"ESP32": latest}))

    result = use_case.execute("ESP32", "1.0.0")

    assert result.update_available is False
    assert result.version is None
    assert result.download_url is None


def test_execute_reports_update_with_signature_and_download_url():
    latest = make_firmware(version="1.2.0", firmware_id=42)
    use_case = CheckUpdate(FakeFirmwareRepository({"ESP32": latest}))

    result = use_case.execute("ESP32", "1.1.0")

    assert result.update_available is True
    assert result.model == "ESP32"
    assert result.version == "1.2.0"
    assert result.signature == latest.signature
    assert result.download_url == "/api/download/42"


def test_execute_checks_the_requested_model_only():
    other_model_latest = make_firmware(model="ESP32-S3", version="9.9.9")
    use_case = CheckUpdate(FakeFirmwareRepository({"ESP32-S3": other_model_latest}))

    with pytest.raises(ModelNotFound):
        use_case.execute("ESP32", "1.0.0")
