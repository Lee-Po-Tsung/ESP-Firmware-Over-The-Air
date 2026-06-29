"""FastAPI application entry point.

Run locally with:  uv run uvicorn main:app --reload --app-dir backend
"""

from __future__ import annotations

from api.routes import router
from fastapi import FastAPI

app = FastAPI(title="ESP OTA Backend", version="0.1.0")
app.include_router(router)
