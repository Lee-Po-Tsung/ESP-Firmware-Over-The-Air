"""Decide whether a device should update.

Given a device's model and its current version, finds the latest firmware for
that model and returns its download details only when it is strictly newer.
A check-in that carries a device id is also recorded, which is what feeds the
dashboard's device page.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from domain import signing
from domain.models import Device
from ports.repository import DeviceRepository, FirmwareRepository


@dataclass
class CheckUpdateResult:
    update_available: bool
    model: str | None = None
    version: str | None = None
    signature: str | None = None
    download_url: str | None = None


class ModelNotFound(Exception):
    """Raised when the requested model has no firmware on record (the API returns HTTP 403)."""


class CheckUpdate:
    def __init__(self, repository: FirmwareRepository, devices: DeviceRepository) -> None:
        self._repo = repository
        self._devices = devices

    def execute(
        self, model: str, current_version: str, device_id: str | None = None
    ) -> CheckUpdateResult:
        # Record the check-in before the firmware lookup, so devices whose
        # model has no published firmware yet still appear on the device page.
        if device_id:
            self._devices.upsert(
                Device(
                    device_id=device_id,
                    model=model,
                    current_version=current_version,
                    last_seen=datetime.now(timezone.utc),
                )
            )

        latest = self._repo.get_latest_for_model(model)
        if latest is None:
            raise ModelNotFound(model)

        if not signing.compare_version(latest.version, current_version):
            return CheckUpdateResult(update_available=False)

        return CheckUpdateResult(
            update_available=True,
            model=model,
            version=latest.version,
            signature=latest.signature,
            download_url=f"/api/download/{latest.id}",
        )
