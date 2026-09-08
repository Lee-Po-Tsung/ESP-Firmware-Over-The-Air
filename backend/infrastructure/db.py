"""SQLAlchemy setup and the database table definitions.

Builds the engine and session factory, and declares the `firmware`,
`devices` and `device_events` tables. `sqlite_repo.py` converts between these
table rows and the domain dataclasses.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from config import get_settings
from sqlalchemy import Boolean, DateTime, Index, Integer, String, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FirmwareRow(Base):
    __tablename__ = "firmware"

    # Both identity axes are enforced here, not just in the use case: the
    # sha256 check there reads before it writes, so two concurrent uploads of
    # one binary both see nothing and both proceed.
    __table_args__ = (
        Index("uq_firmware_model_version", "model", "version", unique=True),
        Index("uq_firmware_model_sha256", "model", "sha256", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[str] = mapped_column(String, nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    # Nullable: rows predating migration 0004 have no name to show.
    original_filename: Mapped[str | None] = mapped_column(String, nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    # Mapper default: `sqlite_repo.add` does not pass `active`, and a freshly
    # uploaded firmware is always live.
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    signature: Mapped[str] = mapped_column(String, nullable=False)
    sha256: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


class DeviceRow(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    model: Mapped[str] = mapped_column(String, nullable=False)
    current_version: Mapped[str | None] = mapped_column(String, nullable=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    poll_interval_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rssi: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ip: Mapped[str | None] = mapped_column(String, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)
    failed_attempts: Mapped[int | None] = mapped_column(Integer, nullable=True)


class DeviceEventRow(Base):
    """Append-only OTA history. Nothing updates or deletes a row here.

    A check-in that carries no news is not recorded. Devices poll every few
    seconds, so writing a row per check-in would add tens of thousands per
    device per day, all saying what `devices.last_seen` already says. A `check`
    row is written only when the server had an update to offer; a check-in on a
    version that changed writes `success` or `rollback` instead.

    `device_id` is the reported string rather than a foreign key to `devices`,
    so an event outlives the row it describes and a download that cannot be
    attributed still records.
    """

    __tablename__ = "device_events"

    # Reads are always "this device's history, newest first".
    __table_args__ = (Index("ix_device_events_device_id_id", "device_id", "id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[str | None] = mapped_column(String, nullable=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    from_version: Mapped[str | None] = mapped_column(String, nullable=True)
    to_version: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, nullable=False)


def make_engine():
    url = make_url(get_settings().database_url)
    # Derived from the URL rather than from `db_path`, so setting DATABASE_URL
    # cannot leave the engine opening one file while the directory of another
    # gets created. SQLite is the only backend with a directory to create, and
    # it will not create one itself; `sqlite://` alone means in-memory.
    if url.drivername.startswith("sqlite") and url.database:
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(url, future=True)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
