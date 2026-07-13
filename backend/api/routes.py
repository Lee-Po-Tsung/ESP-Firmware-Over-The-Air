"""HTTP endpoints for the OTA server.

Device protocol:

- `POST /api/check`
- `GET /api/download/{id}`

plus `POST /firmware/upload` for the admin frontend to publish signed firmware.
Each handler reads the request, calls a use case, and shapes the response. Field
names and status codes follow what the ESP32 firmware in `esp32/main/ota.cpp`
expects.
"""

from __future__ import annotations

import datetime

from application.check_update import CheckUpdate, ModelNotFound
from application.upload_firmware import UploadFirmware, UploadFirmwareRequest
from config import Settings, get_settings
from domain.models import Firmware
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from ports.repository import FirmwareRepository
from ports.storage import StorageBackend
from pydantic import BaseModel

from api.deps import (
    get_check_update,
    get_firmware_repository,
    get_storage,
    get_upload_firmware,
    require_admin_key,
)

router = APIRouter()

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
        result = use_case.execute(body.model, body.version)
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


@router.get("/api/firmware/list")
def firmware_list_api(
    repo: FirmwareRepository = Depends(get_firmware_repository),
) -> list[Firmware]:
    return repo.list_all()


"""
Admin firmware upload
"""


@router.post("/firmware/upload", include_in_schema=False)
def upload(
    model: str = Form(...),
    version: str = Form(...),
    admin_key: str = Form(...),
    firmware: UploadFile = File(...),
    use_case: UploadFirmware = Depends(get_upload_firmware),
    settings: Settings = Depends(get_settings),
) -> dict:
    require_admin_key(admin_key, settings)

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
