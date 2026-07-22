"""Handle an admin uploading a new firmware build.

Stores the uploaded file, computes its SHA-256, signs the `model|version|sha256`
manifest with the private key, and saves a firmware record pointing at the file.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain import signing
from domain.firmware_image import validate_image
from domain.models import Firmware
from ports.repository import (
    FirmwareAlreadyExists,
    FirmwareBinaryAlreadyExists,
    FirmwareRepository,
)
from ports.storage import StorageBackend


@dataclass
class UploadFirmwareRequest:
    model: str
    version: str
    original_filename: str
    data: bytes
    timestamp: str  # caller-supplied "%y%m%d_%H%M%S" prefix (kept for filename parity)


class UploadFirmware:
    def __init__(
        self,
        repository: FirmwareRepository,
        storage: StorageBackend,
        private_key_pem: bytes,
    ) -> None:
        self._repo = repository
        self._storage = storage
        self._private_key_pem = private_key_pem

    def execute(self, req: UploadFirmwareRequest) -> Firmware:
        validate_image(req.data)

        sha256_hex = signing.calculate_sha256_bytes(req.data)
        duplicate = self._repo.get_by_sha256(req.model, sha256_hex)
        if duplicate is not None:
            # A device reports the FIRMWARE_VERSION compiled into its image, so
            # the same bytes under two versions leaves it re-reporting the old
            # one and reflashing on every check.
            raise FirmwareBinaryAlreadyExists(req.model, duplicate.version)

        filename = f"{req.timestamp}_{req.original_filename}"
        self._storage.put(filename, req.data)

        signature = signing.sign_manifest(req.model, req.version, sha256_hex, self._private_key_pem)

        firmware = Firmware(
            model=req.model,
            version=req.version,
            filename=filename,
            signature=signature,
            sha256=sha256_hex,
        )
        try:
            return self._repo.add(firmware)
        except FirmwareAlreadyExists:
            # Delete the duplicate firmware, and raise the Exception again
            # for `/firmware/upload`
            self._storage.delete(filename)
            raise
