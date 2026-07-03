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

from domain.models import Firmware
from application.check_update import CheckUpdate, ModelNotFound
from application.upload_firmware import UploadFirmware, UploadFirmwareRequest
from config import Settings, get_settings
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status, Cookie, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from ports.repository import FirmwareRepository
from ports.storage import StorageBackend
from pydantic import BaseModel
from google.oauth2 import id_token
from google.auth.transport import requests
from uuid import uuid4
import requests # may use httpx in future for async

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
def firmware_list(
    repo: FirmwareRepository = Depends(get_firmware_repository),
) -> list[Firmware]:
    return repo.list_all()

@router.post("/api/auth/google")
def google_oauth(
    client_id: str = Form(...),
    credential: str = Form(...),
    g_csrf_token: str = Form(...),
    g_csrf_token_cookie: str | None = Cookie(None, alias="g_csrf_token"),
    settings = Depends(get_settings)
):  
    WEB_CLIENT_ID = settings.google_client_id
    FRONTEND_URL = settings.frontend_url

    if not FRONTEND_URL:
        raise Exception("Missing FRONTEND_URL in .env file")
    
    # CSRF
    if not g_csrf_token or not g_csrf_token_cookie or g_csrf_token != g_csrf_token_cookie:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="CSRF token does not match"
        )

    if not credential:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Missing credential"
        )

    if not client_id or not WEB_CLIENT_ID or client_id != WEB_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid client ID or missing client ID"
        ) 

    try:
        try:
            idinfo = id_token.verify_oauth2_token(
                credential,
                requests.Request(),
                WEB_CLIENT_ID,
                clock_skew_in_seconds=10 # fastapi need about 5s, otherwise clock faster than google site and then error.
            )
        except Exception as e:
            print(repr(e))
            raise

        # google_id = idinfo['sub']
        # email = idinfo.get('email')
        # name = idinfo.get('name')
        # picture = idinfo.get('picture')
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid or expired Google sign-in credentials."
        )

    # db save userdata

    # stmt = select(User).where(User.google_id == google_id)
    # user = db.execute(stmt).scalar_one_or_none()

    # if not user:
    #     user = User(
    #         google_id=google_id,
    #         email=email,
    #         name=name,
    #         picture=picture,
    #     )

    #     db.add(user)
    #     db.commit()
    #     db.refresh(user)

    response = RedirectResponse(FRONTEND_URL, status_code=status.HTTP_302_FOUND)

    # create session token (PyJWT)

    # iat = datetime.now(timezone.utc)
    # exp = iat + timedelta(days=1)
    # my_site_payload = {
    #     "sub": str(user.id),
    #     "exp": exp,
    #     "iat": iat
    # }
    # my_site_token = jwt.encode(my_site_payload, SECRET_KEY, algorithm=ALGORITHM)

    my_site_token = "123"

    response.set_cookie(
        key="_token", 
        value=my_site_token, 
        httponly=True,
        samesite="lax"
    )

    return response

@router.get("/api/auth/github")
def github_oauth(
    code: str,
    state: str,
    request: Request,
    state_cookie: str | None = Cookie(None, alias="_state"),
    settings = Depends(get_settings)
):  
    WEB_CLIENT_ID = settings.github_client_id
    WEB_CLIENT_SECRET = settings.github_client_secret
    FRONTEND_URL = settings.frontend_url

    base = str(request.base_url).rstrip("/")
    redirect_uri = f"{base}{request.url.path}"

    if not code:
        raise  HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Fail to fetch github code."
        )

    if not FRONTEND_URL:
        raise Exception("Missing FRONTEND_URL in .env file")

    if not WEB_CLIENT_ID:
        raise Exception("Missing WEB_CLIENT_ID in .env file")

    if not WEB_CLIENT_SECRET:
        raise Exception("Missing WEB_CLIENT_SECRET in .env file")

    if not state_cookie or not state or state_cookie != state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid or missing state."
        ) 


    data = {
        "client_id": WEB_CLIENT_ID,
        "client_secret": WEB_CLIENT_SECRET,
        "code": code,
        "redirect_uri": redirect_uri
    }

    github_token = requests.post(
        "https://github.com/login/oauth/access_token", 
        json=data,
        headers={"Accept": "application/json"}
    )

    if not github_token.ok:
        raise  HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Fail to fetch github access token."
        )
    access_token = github_token.json()["access_token"]

    user_data = requests.get("https://api.github.com/user", headers={"Authorization": f"Bearer {access_token}"})

    if not user_data.ok:
        raise  HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Fail to fetch user data from github."
        )

    print(user_data.json())

    response = RedirectResponse(FRONTEND_URL, status_code=status.HTTP_302_FOUND)
    my_site_token = "123"

    response.set_cookie(
        key="_token", 
        value=my_site_token, 
        httponly=True,
        samesite="lax"
    )

    return response

@router.get("/api/auth/github/url")
def gen_github_url(
    request: Request,
    response: Response,
    settings = Depends(get_settings)
):  
    WEB_CLIENT_ID = settings.github_client_id

    if not WEB_CLIENT_ID:
        raise Exception("Missing WEB_CLIENT_ID in .env file")
    
    state = uuid4().hex
    response.set_cookie(
        key="_state",
        value=state,
        httponly=True,
        samesite="lax"
    )

    base = str(request.base_url).rstrip("/")
    path = router.url_path_for("github_oauth")
    redirect_uri = f"{base}{path}"

    url = "https://github.com/login/oauth/authorize?client_id={}&redirect_uri={}&scope={}&state={}".format(
        WEB_CLIENT_ID,
        redirect_uri,
        "%20".join(["user:email"]),
        state
    )

    return {"url": url}

@router.get("/api/user")
def get_user_info(
    token: str | None = Cookie(None, alias="_token")
):
    if not token:
        return {"status": 0, "msg": "not login"}

    # try:
    #     payload = jwt.decode(my_token, SECRET_KEY, algorithms=[ALGORITHM])
    #     uid_str = payload.get("sub")
    #     uid = int(uid_str)
    # except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValueError, TypeError):
    #     raise HTTPException(status_code=401, detail="Invalid or expired session.")

    # stmt = select(User).where(User.id == uid)
    # user_in_db = db.execute(stmt).scalar_one_or_none()

    # if user_in_db is None:
    #     return {"status": 0, "msg": "not login"}
        
    return {
        "status": 1, 
        "msg": "login",
        # "email": user_in_db.email,
        # "name": user_in_db.name,
        # "picture": user_in_db.picture
    }

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
