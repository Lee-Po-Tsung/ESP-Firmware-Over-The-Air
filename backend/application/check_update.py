"""Decide whether a device should update.

Given a device's model and its current version, finds the latest firmware for
that model and returns its download details only when it is strictly newer.
A check-in that carries a device id is also recorded, which is what feeds the
dashboard's device page.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import quote

from domain import ota_history, signing
from domain.models import Device, DeviceEvent, EventType
from ports.repository import DeviceEventRepository, DeviceRepository, FirmwareRepository


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
    last_error: str | None = None
    failed_attempts: int | None = None


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
    def __init__(
        self,
        repository: FirmwareRepository,
        devices: DeviceRepository,
        events: DeviceEventRepository,
    ) -> None:
        self._repo = repository
        self._devices = devices
        self._events = events

    def _offer_is_news(self, device_id: str, current: str, offered: str) -> bool:
        """Whether this offer says anything the log does not already hold.

        The same offer stands on every poll until the device acts on it, so a
        device that cannot flash would otherwise write a row every few seconds
        forever. Only the most recent event is consulted: a download, success
        or rollback in between means the device did something, and the offer
        that follows is a new one.
        """
        recent = self._events.list_for_device(device_id, limit=1)
        if not recent:
            return True
        last = recent[0]
        return not (
            last.event_type is EventType.CHECK
            and last.from_version == current
            and last.to_version == offered
        )

    def execute(self, req: CheckUpdateRequest) -> CheckUpdateResult:
        # Read before the upsert overwrites it. This is the only moment the
        # previous reported version is still available, and the whole event log
        # is built out of the difference between it and what just arrived.
        previous = self._devices.get_by_device_id(req.device_id) if req.device_id else None
        previous_version = previous.current_version if previous else None

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
                    last_error=req.last_error,
                    failed_attempts=req.failed_attempts,
                )
            )
            transition = ota_history.classify_version_change(previous_version, req.version)
            if transition:
                self._events.add(
                    DeviceEvent(
                        device_id=req.device_id,
                        event_type=transition,
                        from_version=previous_version,
                        to_version=req.version,
                    )
                )

        latest = self._repo.get_latest_for_model(req.model)
        if latest is None:
            raise ModelNotFound(req.model)

        if not signing.compare_version(latest.version, req.version):
            return CheckUpdateResult(update_available=False)

        if req.device_id and self._offer_is_news(req.device_id, req.version, latest.version):
            self._events.add(
                DeviceEvent(
                    device_id=req.device_id,
                    event_type=EventType.CHECK,
                    from_version=req.version,
                    to_version=latest.version,
                )
            )

        return CheckUpdateResult(
            update_available=True,
            model=req.model,
            version=latest.version,
            signature=latest.signature,
            # The device follows this verbatim (`ota.cpp:392`), so the id it
            # already reported rides along and the download can be attributed
            # without the firmware sending anything new.
            download_url=(
                f"/api/download/{latest.id}?device_id={quote(req.device_id)}"
                if req.device_id
                else f"/api/download/{latest.id}"
            ),
        )
