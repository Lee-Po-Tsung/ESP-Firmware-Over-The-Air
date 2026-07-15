"""SQLite-backed reads and writes for firmware and device records.

Implements the interfaces in `ports/repository.py` using SQLAlchemy, and maps
each table row to and from the domain dataclasses.
"""

from __future__ import annotations

from domain.models import Device, Firmware, Role, User
from ports.repository import (
    DeviceRepository,
    FirmwareRepository,
    UserAlreadyExists,
    UserRepository,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from infrastructure.db import DeviceRow, FirmwareRow, UserRow


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


def _to_device(row: DeviceRow) -> Device:
    return Device(
        id=row.id,
        device_id=row.device_id,
        model=row.model,
        current_version=row.current_version,
        last_seen=row.last_seen,
    )


def _to_user(row: UserRow) -> User:
    return User(
        id=row.id,
        username=row.username,
        password_hash=row.password_hash,
        role=Role(row.role),
        created_at=row.created_at,
    )


class SqliteUserRepository(UserRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, user: User) -> User:
        row = UserRow(
            username=user.username,
            password_hash=user.password_hash,
            role=user.role.value,
        )
        self._session.add(row)
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise UserAlreadyExists(user.username) from exc
        self._session.refresh(row)
        return _to_user(row)

    def get_by_id(self, user_id: int) -> User | None:
        row = self._session.get(UserRow, user_id)
        return _to_user(row) if row else None

    def get_by_username(self, username: str) -> User | None:
        row = self._session.scalar(select(UserRow).where(UserRow.username == username))
        return _to_user(row) if row else None


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
        return _to_device(row) if row else None

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
        return _to_device(row)

    def list_all(self) -> list[Device]:
        # SQLite sorts NULL as smallest, so never-seen devices land last on desc.
        rows = self._session.scalars(
            select(DeviceRow).order_by(DeviceRow.last_seen.desc(), DeviceRow.id.desc())
        ).all()
        return [_to_device(r) for r in rows]
