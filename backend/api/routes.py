"""HTTP endpoints for the OTA server.

Device protocol:

- `POST /api/check`
- `GET /api/download/{id}`

plus `POST /firmware/upload` for the admin frontend to publish signed firmware
and `GET /api/devices` for the dashboard device page.
Each handler reads the request, calls a use case, and shapes the response. Field
names and status codes follow what the ESP32 firmware in `esp32/main/ota.cpp`
expects.
"""

from __future__ import annotations

import datetime

from application.auth import AuthenticateUser, InvalidCredentials, RegisterUser, RegisterUserRequest
from application.check_update import CheckUpdate, ModelNotFound
from application.upload_firmware import UploadFirmware, UploadFirmwareRequest
from domain.auth import MAX_PASSWORD_BYTES
from domain.models import Firmware
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from ports.repository import DeviceRepository, FirmwareRepository, UserAlreadyExists
from ports.storage import StorageBackend
from pydantic import BaseModel, Field, field_validator

from api.deps import (
    get_authenticate_user,
    get_check_update,
    get_current_user,
    get_device_repository,
    get_firmware_repository,
    get_register_user,
    get_storage,
    get_upload_firmware,
    require_admin,
)

router = APIRouter()

"""
Auth
"""


class RegisterRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def _fits_bcrypt(cls, v: str) -> str:
        if len(v.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError(f"password must be at most {MAX_PASSWORD_BYTES} bytes")
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest,
    use_case: RegisterUser = Depends(get_register_user),
) -> dict:
    """Open self-signup, always as an Operator. Admins are seeded via scripts/create_user.py."""
    try:
        user = use_case.execute(RegisterUserRequest(username=body.username, password=body.password))
    except UserAlreadyExists as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username taken") from exc
    return {"id": user.id, "username": user.username, "role": user.role.value}


@router.post("/api/auth/login")
def login(
    body: LoginRequest,
    use_case: AuthenticateUser = Depends(get_authenticate_user),
) -> TokenResponse:
    try:
        token = use_case.execute(body.username, body.password)
    except InvalidCredentials as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return TokenResponse(access_token=token)


"""
Device protocol
"""


class CheckRequest(BaseModel):
    model: str
    version: str
    device_id: str | None = None


@router.post("/api/check")
def check_update(
    body: CheckRequest,
    use_case: CheckUpdate = Depends(get_check_update),
) -> dict:
    try:
        result = use_case.execute(body.model, body.version, body.device_id)
    except ModelNotFound as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN) from exc

    if not result.update_available:
        return {"update_available": False}

    return {
        "update_available": True,
        "version": result.version,
        "signature": result.signature,
        "download_url": result.download_url,
    }


@router.get("/api/download/{firmware_id}")
def download_firmware(
    firmware_id: int,
    repo: FirmwareRepository = Depends(get_firmware_repository),
    storage: StorageBackend = Depends(get_storage),
) -> Response:
    firmware = repo.get_by_id(firmware_id)
    if firmware is None or not storage.exists(firmware.filename):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    data = storage.get(firmware.filename)
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{firmware.filename}"'},
    )


@router.get("/api/firmware/list", dependencies=[Depends(get_current_user)])
def firmware_list_api(
    repo: FirmwareRepository = Depends(get_firmware_repository),
) -> list[Firmware]:
    return repo.list_all()


"""
Dashboard device page
"""


@router.get("/api/devices", dependencies=[Depends(get_current_user)])
def device_list_api(repo: DeviceRepository = Depends(get_device_repository)) -> list[dict]:
    # SQLite hands back naive datetimes; they are UTC by construction, so stamp
    # the offset or browsers would parse the ISO string as local time.
    def _iso_utc(dt: datetime.datetime | None) -> str | None:
        return dt.replace(tzinfo=datetime.timezone.utc).isoformat() if dt else None

    return [
        {
            "id": d.id,
            "device_id": d.device_id,
            "model": d.model,
            "current_version": d.current_version,
            "last_seen": _iso_utc(d.last_seen),
        }
        for d in repo.list_all()
    ]


"""
Admin firmware upload
"""


# Upload firmware require admin privilege
@router.post("/firmware/upload", include_in_schema=False, dependencies=[Depends(require_admin)])
def upload(
    model: str = Form(...),
    version: str = Form(...),
    firmware: UploadFile = File(...),
    use_case: UploadFirmware = Depends(get_upload_firmware),
) -> dict:
    timestamp = datetime.datetime.now().strftime("%y%m%d_%H%M%S")
    data = firmware.file.read()
    use_case.execute(
        UploadFirmwareRequest(
            model=model,
            version=version,
            original_filename=firmware.filename or "firmware.bin",
            data=data,
            timestamp=timestamp,
        )
    )
    return {"status": "ok"}
