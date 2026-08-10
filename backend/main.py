"""FastAPI application entry point.

Run locally with:  uv run uvicorn main:app --reload --app-dir backend
"""

from __future__ import annotations

from api.routes import router
from config import get_settings
from fastapi import FastAPI

# Fail at boot, not at first login, if JWT_SECRET is missing. Scripts and
# alembic import config without this check so they run before .env exists.
_ = get_settings().jwt_secret

# Same reason, one setup step later. The signing key is read while FastAPI is
# resolving the upload route's dependencies, which is before the handler body
# and so before any of its error mapping; a missing key there surfaces as a
# bare 500 pointing at deps.py rather than at the step that was skipped.
_ = get_settings().read_private_key()

app = FastAPI(title="ESP OTA Backend", version="0.1.0")
app.include_router(router)
