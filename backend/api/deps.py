"""Assembles what the route handlers need and exposes it as FastAPI dependencies.

Opens a database session per request, builds the repositories, storage and use
cases on top of it, and provides the shared admin-key check used to gate uploads.
"""

from __future__ import annotations

from collections.abc import Iterator

from application.check_update import CheckUpdate
from application.upload_firmware import UploadFirmware
from config import Settings, get_settings
from fastapi import Depends, HTTPException, status
from infrastructure.db import SessionLocal
from infrastructure.local_storage import LocalStorage
from infrastructure.sqlite_repo import SqliteFirmwareRepository
from ports.repository import FirmwareRepository
from ports.storage import StorageBackend
from sqlalchemy.orm import Session


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_firmware_repository(db: Session = Depends(get_db)) -> FirmwareRepository:
    return SqliteFirmwareRepository(db)


def get_storage(settings: Settings = Depends(get_settings)) -> StorageBackend:
    return LocalStorage(settings.firmware_dir)


def get_check_update(
    repo: FirmwareRepository = Depends(get_firmware_repository),
) -> CheckUpdate:
    return CheckUpdate(repo)


def get_upload_firmware(
    repo: FirmwareRepository = Depends(get_firmware_repository),
    storage: StorageBackend = Depends(get_storage),
    settings: Settings = Depends(get_settings),
) -> UploadFirmware:
    return UploadFirmware(repo, storage, settings.read_private_key())


def require_admin_key(admin_key: str, settings: Settings) -> None:
    """Gate write endpoints behind the shared admin key (replaced by real auth in M2).

    A plain helper called from the handler, not a FastAPI dependency: the handler
    already has `settings` and the key arrives as a form field, not a header.
    """
    if admin_key != settings.admin_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid admin key",
        )
