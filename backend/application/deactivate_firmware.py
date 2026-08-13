"""Withdraw a published firmware version.

Clears the `active` flag on a firmware row so `get_latest_for_model` no longer
offers it to devices. Idempotent: deactivating an already-inactive version
succeeds and changes nothing. Nothing here touches storage, because one blob
can back several rows and a row whose blob is gone 404s on download.
"""

from __future__ import annotations

from domain.models import Firmware
from ports.repository import FirmwareNotFound, FirmwareRepository


class DeactivateFirmware:
    def __init__(self, repository: FirmwareRepository) -> None:
        self._repo = repository

    def execute(self, firmware_id: int) -> Firmware:
        firmware = self._repo.deactivate(firmware_id)
        if firmware is None:
            raise FirmwareNotFound(firmware_id)
        return firmware
