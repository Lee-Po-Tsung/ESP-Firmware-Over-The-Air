"""HTTP endpoints for the OTA server.

Device protocol:

- `POST /api/check`
- `GET /api/download/{id}`

with a small HTML page for listing and uploading firmware by hand. Each handler reads
the request, calls a use case, and shapes the response. Field names and status
codes follow what the ESP32 firmware in `esp32/main/ota.cpp` expects.
"""

from __future__ import annotations

import datetime
import html

from application.check_update import CheckUpdate, ModelNotFound
from application.upload_firmware import UploadFirmware, UploadFirmwareRequest
from config import Settings, get_settings
from domain.models import Firmware
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
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
    # "ID" carries the device *model*, matching the on-device payload verbatim.
    ID: str
    version: str


@router.post("/api/check")
def check_update(
    body: CheckRequest,
    use_case: CheckUpdate = Depends(get_check_update),
) -> dict:
    try:
        result = use_case.execute(body.ID, body.version)
    except ModelNotFound as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN) from exc

    if not result.update_available:
        return {"update_available": False}

    return {
        "update_available": True,
        "ID": result.model,
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
Simple HTML test page
"""


def _render_page(rows_html: str, message: str = "") -> str:
    banner = f"<p><strong>{html.escape(message)}</strong></p>" if message else ""
    return f"""<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><title>Firmware</title></head><body>
{banner}
<form method='post' action='/firmware/upload' enctype="multipart/form-data">
<label for='model'>型號</label><input type='text' name='model'/><br>
<label for='version'>版本</label><input type='text' name='version'/><br>
<label for='admin_key'>管理員金鑰</label><input type='password' name='admin_key'/><br>
<label for='firmware'>韌體檔案</label><input type='file' name='firmware'/><br>
<input type='submit'></form><br>
<table border="1"><thead><tr><th>型號</th><th>版本</th><th>檔名</th></tr></thead>
<tbody>{rows_html}</tbody>
</table>
</body></html>"""


@router.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/firmware")


@router.get("/firmware", response_class=HTMLResponse, include_in_schema=False)
def firmware_list(
    repo: FirmwareRepository = Depends(get_firmware_repository),
) -> HTMLResponse:
    rows = []
    for fw in repo.list_all():
        rows.append(
            "<tr>"
            f"<td>{html.escape(fw.model)}</td>"
            f"<td>{html.escape(fw.version)}</td>"
            f"<td>{html.escape(fw.filename)}</td>"
            "</tr>"
        )
    return HTMLResponse(_render_page("".join(rows)))


@router.post("/firmware/upload", response_class=HTMLResponse, include_in_schema=False)
def upload(
    model: str = Form(...),
    version: str = Form(...),
    admin_key: str = Form(...),
    firmware: UploadFile = File(...),
    use_case: UploadFirmware = Depends(get_upload_firmware),
    settings: Settings = Depends(get_settings),
) -> HTMLResponse:
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
    return HTMLResponse(
        _render_page("", message="上傳成功"),
        status_code=status.HTTP_303_SEE_OTHER,
    )
