"""Handle an admin uploading a new firmware build.

Stores the uploaded file, computes its SHA-256, signs the `model|version|sha256`
manifest with the private key, and saves a firmware record pointing at the file.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain import signing
from domain.models import Firmware
from ports.repository import FirmwareRepository
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
        filename = f"{req.timestamp}_{req.original_filename}"

        self._storage.put(filename, req.data)

        sha256_hex = signing.calculate_sha256_bytes(req.data)
        signature = signing.sign_manifest(req.model, req.version, sha256_hex, self._private_key_pem)

        firmware = Firmware(
            model=req.model,
            version=req.version,
            filename=filename,
            signature=signature,
            sha256=sha256_hex,
        )
        return self._repo.add(firmware)
