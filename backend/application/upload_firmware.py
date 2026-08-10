"""Handle an admin uploading a new firmware build.

Computes the uploaded file's SHA-256, signs the `model|version|sha256` manifest
with the private key, stores the bytes under a name derived from that hash, and
saves a firmware record pointing at them.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain import signing
from domain.firmware_image import validate_image
from domain.models import Firmware
from ports.repository import FirmwareBinaryAlreadyExists, FirmwareRepository
from ports.storage import StorageBackend


@dataclass
class UploadFirmwareRequest:
    model: str
    version: str
    original_filename: str
    data: bytes


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
        signing.validate_manifest_fields(req.model, req.version)
        validate_image(req.data)

        sha256_hex = signing.calculate_sha256_bytes(req.data)
        duplicate = self._repo.get_by_sha256(req.model, sha256_hex)
        if duplicate is not None:
            # A device reports the FIRMWARE_VERSION compiled into its image, so
            # the same bytes under two versions leaves it re-reporting the old
            # one and reflashing on every check.
            raise FirmwareBinaryAlreadyExists(req.model, duplicate.version)

        # Sign before storing, so a missing or corrupt private key writes nothing.
        signature = signing.sign_manifest(req.model, req.version, sha256_hex, self._private_key_pem)

        # Named after its contents, so a collision implies identical bytes and
        # the overwrite in `put` is harmless by construction.
        filename = f"{sha256_hex}.bin"
        self._storage.put(filename, req.data)

        # A rejected `add` leaves the blob in place: it is shared by every row
        # with these bytes and nothing here can prove it unreferenced. The two
        # failures are not symmetric. An orphan blob wastes disk, while a row
        # whose blob was deleted under it 404s and reboot-loops every device
        # mid-download.
        return self._repo.add(
            Firmware(
                model=req.model,
                version=req.version,
                filename=filename,
                original_filename=req.original_filename,
                signature=signature,
                sha256=sha256_hex,
            )
        )
