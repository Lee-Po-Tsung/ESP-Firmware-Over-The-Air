"""SQLAlchemy setup and the database table definitions.

Builds the engine and session factory, and declares the `firmware` and
`devices` tables. `sqlite_repo.py` converts between these table rows and the
domain dataclasses.
"""

from __future__ import annotations

from datetime import datetime, timezone

from config import get_settings
from sqlalchemy import DateTime, Index, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FirmwareRow(Base):
    __tablename__ = "firmware"

    # `model|version` should all be unique index.
    __table_args__ = (Index("uq_firmware_model_version", "model", "version", unique=True),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[str] = mapped_column(String, nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
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


def make_engine():
    settings = get_settings()
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(settings.database_url, future=True)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
