from __future__ import annotations

import base64

import pytest
from application.upload_firmware import UploadFirmware, UploadFirmwareRequest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from domain import signing
from domain.models import Firmware
from ports.repository import FirmwareAlreadyExists


class FakeFirmwareRepository:
    """In-memory stand-in for `FirmwareRepository`; records what gets added."""

    def __init__(self) -> None:
        self.added: list[Firmware] = []

    def add(self, firmware: Firmware) -> Firmware:
        firmware.id = len(self.added) + 1
        self.added.append(firmware)
        return firmware

    def get_by_id(self, firmware_id: int) -> Firmware | None:
        raise NotImplementedError

    def get_latest_for_model(self, model: str) -> Firmware | None:
        raise NotImplementedError

    def list_all(self) -> list[Firmware]:
        raise NotImplementedError


class RejectingFirmwareRepository(FakeFirmwareRepository):
    """Stands in for the unique (model, version) index rejecting an add."""

    def add(self, firmware: Firmware) -> Firmware:
        raise FirmwareAlreadyExists(firmware.model, firmware.version)


class FakeStorage:
    """In-memory stand-in for `StorageBackend`."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def put(self, filename: str, data: bytes) -> None:
        self.files[filename] = data

    def get(self, filename: str) -> bytes:
        return self.files[filename]

    def delete(self, filename: str) -> None:
        self.files.pop(filename, None)

    def exists(self, filename: str) -> bool:
        return filename in self.files


@pytest.fixture(scope="module")
def keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return private_key, private_pem


def test_execute_stores_data_under_timestamped_filename(keypair):
    _, private_pem = keypair
    repo, storage = FakeFirmwareRepository(), FakeStorage()
    use_case = UploadFirmware(repo, storage, private_pem)

    use_case.execute(
        UploadFirmwareRequest(
            model="ESP32",
            version="1.0.0",
            original_filename="firmware.bin",
            data=b"binary contents",
            timestamp="260101_000000",
        )
    )

    assert storage.files == {"260101_000000_firmware.bin": b"binary contents"}


def test_execute_records_firmware_with_matching_hash_and_verifiable_signature(keypair):
    private_key, private_pem = keypair
    repo, storage = FakeFirmwareRepository(), FakeStorage()
    use_case = UploadFirmware(repo, storage, private_pem)
    data = b"binary contents"

    firmware = use_case.execute(
        UploadFirmwareRequest(
            model="ESP32",
            version="1.0.0",
            original_filename="firmware.bin",
            data=data,
            timestamp="260101_000000",
        )
    )

    assert firmware is repo.added[0]
    assert firmware.model == "ESP32"
    assert firmware.version == "1.0.0"
    assert firmware.filename == "260101_000000_firmware.bin"
    assert firmware.sha256 == signing.calculate_sha256_bytes(data)

    manifest_bytes = signing.build_manifest("ESP32", "1.0.0", firmware.sha256).encode("utf-8")
    private_key.public_key().verify(
        base64.b64decode(firmware.signature),
        manifest_bytes,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )


def test_execute_removes_the_stored_file_when_the_version_is_taken(keypair):
    _, private_pem = keypair
    repo, storage = RejectingFirmwareRepository(), FakeStorage()
    use_case = UploadFirmware(repo, storage, private_pem)

    with pytest.raises(FirmwareAlreadyExists):
        use_case.execute(
            UploadFirmwareRequest(
                model="ESP32",
                version="1.0.0",
                original_filename="firmware.bin",
                data=b"binary contents",
                timestamp="260101_000000",
            )
        )

    assert storage.files == {}
