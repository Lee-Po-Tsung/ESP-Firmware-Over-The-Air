"""SQLite-backed reads and writes for firmware and device records.

Implements the interfaces in `ports/repository.py` using SQLAlchemy, and maps
each table row to and from the domain dataclasses.
"""

from __future__ import annotations

from domain.models import Device, Firmware
from ports.repository import DeviceRepository, FirmwareRepository
from sqlalchemy import select
from sqlalchemy.orm import Session

from infrastructure.db import DeviceRow, FirmwareRow


def _version_key(version: str) -> list[int]:
    """Sort key matching `domain.signing.compare_version` semantics."""
    return list(map(int, version.split(".", 2)))


def _to_firmware(row: FirmwareRow) -> Firmware:
    return Firmware(
        id=row.id,
        model=row.model,
        version=row.version,
        filename=row.filename,
        signature=row.signature,
        sha256=row.sha256,
        created_at=row.created_at,
    )


class SqliteFirmwareRepository(FirmwareRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, firmware: Firmware) -> Firmware:
        row = FirmwareRow(
            model=firmware.model,
            version=firmware.version,
            filename=firmware.filename,
            signature=firmware.signature,
            sha256=firmware.sha256,
        )
        self._session.add(row)
        self._session.commit()
        self._session.refresh(row)
        return _to_firmware(row)

    def get_by_id(self, firmware_id: int) -> Firmware | None:
        row = self._session.get(FirmwareRow, firmware_id)
        return _to_firmware(row) if row else None

    def get_latest_for_model(self, model: str) -> Firmware | None:
        rows = self._session.scalars(select(FirmwareRow).where(FirmwareRow.model == model)).all()
        if not rows:
            return None
        latest = max(rows, key=lambda r: _version_key(r.version))
        return _to_firmware(latest)

    def list_all(self) -> list[Firmware]:
        rows = self._session.scalars(
            select(FirmwareRow).order_by(FirmwareRow.created_at.desc(), FirmwareRow.id.desc())
        ).all()
        return [_to_firmware(r) for r in rows]


class SqliteDeviceRepository(DeviceRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_device_id(self, device_id: str) -> Device | None:
        row = self._session.scalar(select(DeviceRow).where(DeviceRow.device_id == device_id))
        if not row:
            return None
        return Device(
            id=row.id,
            device_id=row.device_id,
            model=row.model,
            current_version=row.current_version,
            last_seen=row.last_seen,
        )

    def upsert(self, device: Device) -> Device:
        row = self._session.scalar(select(DeviceRow).where(DeviceRow.device_id == device.device_id))
        if row is None:
            row = DeviceRow(device_id=device.device_id, model=device.model)
            self._session.add(row)
        row.model = device.model
        row.current_version = device.current_version
        row.last_seen = device.last_seen
        self._session.commit()
        self._session.refresh(row)
        return Device(
            id=row.id,
            device_id=row.device_id,
            model=row.model,
            current_version=row.current_version,
            last_seen=row.last_seen,
        )
