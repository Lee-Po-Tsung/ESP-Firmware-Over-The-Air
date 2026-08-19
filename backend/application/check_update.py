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
class CheckUpdateRequest:
    """One check-in. Everything the device chooses to say about itself.

    Only `model` and `version` steer the answer; the rest is recorded and never
    read here, which is why a device that reports none of it still gets a
    correct update decision.

    The telemetry is optional here and required on `api.routes.CheckRequest`.
    That gap is deliberate, not an oversight to tidy up: what the fleet must
    send is a deployment question the HTTP layer answers, while the decision
    this class makes has never needed any of it.
    """

    model: str
    version: str
    device_id: str | None = None
    poll_interval_seconds: int | None = None
    rssi: int | None = None
    ip: str | None = None


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

    def execute(self, req: CheckUpdateRequest) -> CheckUpdateResult:
        # Record the check-in before the firmware lookup, so devices whose
        # model has no published firmware yet still appear on the device page.
        if req.device_id:
            self._devices.upsert(
                Device(
                    device_id=req.device_id,
                    model=req.model,
                    current_version=req.version,
                    last_seen=datetime.now(timezone.utc),
                    poll_interval_seconds=req.poll_interval_seconds,
                    rssi=req.rssi,
                    ip=req.ip,
                )
            )

        latest = self._repo.get_latest_for_model(req.model)
        if latest is None:
            raise ModelNotFound(req.model)

        if not signing.compare_version(latest.version, req.version):
            return CheckUpdateResult(update_available=False)

        return CheckUpdateResult(
            update_available=True,
            model=req.model,
            version=latest.version,
            signature=latest.signature,
            download_url=f"/api/download/{latest.id}",
        )
