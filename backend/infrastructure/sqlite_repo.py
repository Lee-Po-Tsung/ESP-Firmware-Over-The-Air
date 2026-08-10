"""SQLite-backed reads and writes for firmware and device records.

Implements the interfaces in `ports/repository.py` using SQLAlchemy, and maps
each table row to and from the domain dataclasses.
"""

from __future__ import annotations

from datetime import datetime, timezone

from domain.models import Device, Firmware, Role, User
from domain.signing import parse_version
from ports.repository import (
    DeviceRepository,
    FirmwareAlreadyExists,
    FirmwareRepository,
    UserAlreadyExists,
    UserRepository,
)
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from infrastructure.db import DeviceRow, FirmwareRow, UserRow


def _utc(value: datetime | None) -> datetime | None:
    """Re-attach the UTC offset SQLite drops.

    Every timestamp is written as UTC (`db._utcnow`), but SQLite has no
    timezone type and hands the value back naive. Anything serializing a naive
    datetime produces an ISO string with no offset, which a browser reads as
    local time. Stamping here is what keeps that from being each caller's
    problem to remember.
    """
    return value.replace(tzinfo=timezone.utc) if value is not None else None


def _to_firmware(row: FirmwareRow) -> Firmware:
    return Firmware(
        id=row.id,
        model=row.model,
        version=row.version,
        filename=row.filename,
        original_filename=row.original_filename,
        signature=row.signature,
        sha256=row.sha256,
        created_at=_utc(row.created_at),
    )


def _to_device(row: DeviceRow) -> Device:
    return Device(
        id=row.id,
        device_id=row.device_id,
        model=row.model,
        current_version=row.current_version,
        last_seen=_utc(row.last_seen),
    )


def _to_user(row: UserRow) -> User:
    return User(
        id=row.id,
        username=row.username,
        password_hash=row.password_hash,
        role=Role(row.role),
        created_at=_utc(row.created_at),
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
            original_filename=firmware.original_filename,
            signature=firmware.signature,
            sha256=firmware.sha256,
        )
        self._session.add(row)
        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise FirmwareAlreadyExists(firmware.model, firmware.version) from exc
        self._session.refresh(row)
        return _to_firmware(row)

    def get_by_id(self, firmware_id: int) -> Firmware | None:
        row = self._session.get(FirmwareRow, firmware_id)
        return _to_firmware(row) if row else None

    def get_by_sha256(self, model: str, sha256: str) -> Firmware | None:
        row = self._session.scalar(
            select(FirmwareRow).where(FirmwareRow.model == model, FirmwareRow.sha256 == sha256)
        )
        return _to_firmware(row) if row else None

    def get_latest_for_model(self, model: str) -> Firmware | None:
        rows = self._session.scalars(select(FirmwareRow).where(FirmwareRow.model == model)).all()
        if not rows:
            return None
        latest = max(rows, key=lambda r: (parse_version(r.version), r.id))
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
        try:
            self._session.commit()
        except IntegrityError as exc:
            # This is a read followed by a write, and `device_id` is unique, so
            # a second check-in for the same device landing between the two
            # makes one of them lose. Handlers are `def`, so uvicorn runs them
            # on a threadpool and a device retrying mid-flight is enough.
            #
            # The other two write methods here answer their own version of this
            # by raising a domain exception, but neither of them is on the
            # device's path: `main.ino` reboots over a failed check. The winner
            # is the same device reporting moments earlier, so its row is
            # returned as it stands and this check-in is dropped. Rollback
            # expunges the row built above, which is why this reads again
            # instead of refreshing.
            self._session.rollback()
            winner = self._session.scalar(
                select(DeviceRow).where(DeviceRow.device_id == device.device_id)
            )
            if winner is None:
                raise exc
            return _to_device(winner)

        self._session.refresh(row)
        return _to_device(row)

    def list_all(self) -> list[Device]:
        # SQLite sorts NULL as smallest, so never-seen devices land last on desc.
        rows = self._session.scalars(
            select(DeviceRow).order_by(DeviceRow.last_seen.desc(), DeviceRow.id.desc())
        ).all()
        return [_to_device(r) for r in rows]
