"""Assembles what the route handlers need and exposes it as FastAPI dependencies.

Opens a database session per request, builds the repositories, storage and use
cases on top of it, and resolves the bearer token into the current account so
write endpoints can be gated by role.
"""

from __future__ import annotations

from collections.abc import Iterator

from application.auth import AuthenticateUser, RegisterUser
from application.check_update import CheckUpdate
from application.upload_firmware import UploadFirmware
from config import Settings, get_settings
from domain import auth
from domain.models import Role, User
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from infrastructure.db import SessionLocal
from infrastructure.local_storage import LocalStorage
from infrastructure.sqlite_repo import SqliteFirmwareRepository, SqliteUserRepository
from ports.repository import FirmwareRepository, UserRepository
from ports.storage import StorageBackend
from sqlalchemy.orm import Session

bearer_scheme = HTTPBearer(auto_error=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_firmware_repository(db: Session = Depends(get_db)) -> FirmwareRepository:
    return SqliteFirmwareRepository(db)


def get_user_repository(db: Session = Depends(get_db)) -> UserRepository:
    return SqliteUserRepository(db)


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


def get_register_user(repo: UserRepository = Depends(get_user_repository)) -> RegisterUser:
    return RegisterUser(repo)


def get_authenticate_user(
    repo: UserRepository = Depends(get_user_repository),
    settings: Settings = Depends(get_settings),
) -> AuthenticateUser:
    return AuthenticateUser(repo, settings.jwt_secret, settings.jwt_expires_minutes)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    repo: UserRepository = Depends(get_user_repository),
    settings: Settings = Depends(get_settings),
) -> User:
    """Resolve the bearer token into the account it belongs to.

    Rejects a missing, malformed, or expired token, and a token whose account no
    longer exists, all as 401.
    """
    if credentials is None:
        raise _unauthorized("Missing bearer token")
    try:
        user_id, _role = auth.decode_access_token(credentials.credentials, settings.jwt_secret)
    except auth.InvalidToken as exc:
        raise _unauthorized("Invalid or expired token") from exc

    user = repo.get_by_id(user_id)
    if user is None:
        raise _unauthorized("Account no longer exists")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Gate write endpoints behind an admin account."""
    if user.role is not Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return user


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )
