"""Decide whether a device should update.

Given a device's model and its current version, finds the latest firmware for
that model and returns its download details only when it is strictly newer.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain import signing
from ports.repository import FirmwareRepository


@dataclass
class CheckUpdateResult:
    update_available: bool
    model: str | None = None
    version: str | None = None
    signature: str | None = None
    download_url: str | None = None


class ModelNotFound(Exception):
    """Raised when the requested model has no firmware on record (the API returns HTTP 403)."""


class CheckUpdate:
    def __init__(self, repository: FirmwareRepository) -> None:
        self._repo = repository

    def execute(self, model: str, current_version: str) -> CheckUpdateResult:
        latest = self._repo.get_latest_for_model(model)
        if latest is None:
            raise ModelNotFound(model)

        if not signing.compare_version(latest.version, current_version):
            return CheckUpdateResult(update_available=False)

        return CheckUpdateResult(
            update_available=True,
            model=model,
            version=latest.version,
            signature=latest.signature,
            download_url=f"/api/download/{latest.id}",
        )
