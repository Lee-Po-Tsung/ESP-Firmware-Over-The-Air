"""HTTP endpoints for the OTA server.

Device protocol:

- `POST /api/check`
- `GET /api/download/{id}`

plus `POST /firmware/upload` for the admin frontend to publish signed firmware
and `GET /api/devices` for the dashboard device page.
Each handler reads the request, calls a use case, and returns a domain object;
the `response_model` on the route decides which fields reach the wire. Field
names and status codes follow what the ESP32 firmware in `esp32/main/ota.cpp`
expects.
"""

from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

from application.auth import AuthenticateUser, InvalidCredentials, RegisterUser, RegisterUserRequest
from application.check_update import CheckUpdate, ModelNotFound
from application.upload_firmware import UploadFirmware, UploadFirmwareRequest
from domain.auth import MAX_PASSWORD_BYTES
from domain.firmware_image import InvalidFirmwareImage
from domain.models import Role
from domain.signing import InvalidManifestField
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from ports.repository import (
    DeviceRepository,
    FirmwareAlreadyExists,
    FirmwareBinaryAlreadyExists,
    FirmwareRepository,
    UserAlreadyExists,
)
from ports.storage import StorageBackend
from pydantic import BaseModel, ConfigDict, Field, field_validator

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


class _FromDomain(BaseModel):
    """Base for responses read off a domain dataclass.

    Returning the dataclass itself would put every one of its fields on the
    wire, and adding a field to the domain would publish it silently. Naming
    the fields here keeps that decision in the route.
    """

    model_config = ConfigDict(from_attributes=True)


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


class UserResponse(_FromDomain):
    id: int
    username: str
    role: Role


@router.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest,
    use_case: RegisterUser = Depends(get_register_user),
) -> UserResponse:
    """Open self-signup, always as an Operator. Admins are seeded via scripts/create_user.py."""
    try:
        user = use_case.execute(RegisterUserRequest(username=body.username, password=body.password))
    except UserAlreadyExists as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username taken") from exc
    return UserResponse.model_validate(user)


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


class CheckResponse(_FromDomain):
    """`exclude_none` on the route keeps the no-update answer a lone flag.

    `ota.cpp` reads `update_available` first and the rest only when it is true,
    so three explicit nulls would parse the same. Sending them anyway would put
    a shape on the wire that no deployed device was built against.
    """

    update_available: bool
    version: str | None = None
    signature: str | None = None
    download_url: str | None = None


@router.post("/api/check", response_model_exclude_none=True)
def check_update(
    body: CheckRequest,
    use_case: CheckUpdate = Depends(get_check_update),
) -> CheckResponse:
    try:
        result = use_case.execute(body.model, body.version, body.device_id)
    except ModelNotFound as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN) from exc

    return CheckResponse.model_validate(result)


def _content_disposition(filename: str) -> str:
    """Build a Content-Disposition value that survives any stored filename.

    `original_filename` is whatever the uploader's browser sent, and header
    values are latin-1 encoded on the way out, so a non-ASCII name raises
    instead of being sent. RFC 6266 answers this with two parameters: a quoted
    ASCII fallback, and a percent-encoded UTF-8 form that clients prefer when
    they understand it. Anything outside printable ASCII becomes an underscore
    in the fallback, which also keeps a quote or a newline in the name from
    escaping the quoted string.
    """
    ascii_name = "".join(
        c if c.isascii() and c.isprintable() and c not in '"\\' else "_" for c in filename
    )
    # `safe=""`: the default leaves `/` alone, and this is a filename, not a path.
    encoded = quote(filename, safe="")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded}"


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
    # The stored name is a hash. Offer a browser the name it was uploaded under;
    # the device ignores the header and reads the stream.
    download_name = firmware.original_filename or firmware.filename
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": _content_disposition(download_name)},
    )


class FirmwareResponse(_FromDomain):
    id: int
    model: str
    version: str
    filename: str
    original_filename: str | None
    signature: str
    sha256: str
    created_at: datetime


@router.get("/api/firmware/list", dependencies=[Depends(get_current_user)])
def firmware_list_api(
    repo: FirmwareRepository = Depends(get_firmware_repository),
) -> list[FirmwareResponse]:
    return [FirmwareResponse.model_validate(f) for f in repo.list_all()]


"""
Dashboard device page
"""


class DeviceResponse(_FromDomain):
    id: int
    device_id: str
    model: str
    current_version: str | None
    last_seen: datetime | None


@router.get("/api/devices", dependencies=[Depends(get_current_user)])
def device_list_api(
    repo: DeviceRepository = Depends(get_device_repository),
) -> list[DeviceResponse]:
    return [DeviceResponse.model_validate(d) for d in repo.list_all()]


"""
Admin firmware upload
"""


class UploadResponse(BaseModel):
    status: str


# Upload firmware require admin privilege
@router.post("/firmware/upload", include_in_schema=False, dependencies=[Depends(require_admin)])
def upload(
    model: str = Form(...),
    version: str = Form(...),
    firmware: UploadFile = File(...),
    use_case: UploadFirmware = Depends(get_upload_firmware),
) -> UploadResponse:
    data = firmware.file.read()
    try:
        use_case.execute(
            UploadFirmwareRequest(
                model=model,
                version=version,
                original_filename=firmware.filename or "firmware.bin",
                data=data,
            )
        )
    except (InvalidManifestField, InvalidFirmwareImage) as exc:
        # The validator's message names the field that failed, so pass it
        # through rather than flattening every rejection into one string.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FirmwareBinaryAlreadyExists as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This binary was already uploaded as version {exc.existing_version}",
        ) from exc
    except FirmwareAlreadyExists as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Version already exists for this model",
        ) from exc
    return UploadResponse(status="ok")
