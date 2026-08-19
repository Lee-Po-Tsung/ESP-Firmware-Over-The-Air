from __future__ import annotations

import base64
import struct

import pytest
from application.upload_firmware import UploadFirmware, UploadFirmwareRequest
from conftest import FakeFirmwareRepository, FakeStorage
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from domain import signing
from domain.firmware_image import (
    APP_DESC_MAGIC,
    APP_DESC_OFFSET,
    CHIP_ID_OFFSET,
    IMAGE_MAGIC,
    MIN_FIRMWARE_BYTES,
    InvalidFirmwareImage,
)
from domain.models import Firmware
from ports.repository import FirmwareAlreadyExists, FirmwareBinaryAlreadyExists


def valid_image(filler: int = 0) -> bytes:
    """Minimal bytes that clear `validate_image`; the contents carry no meaning.

    Leaves the appended-digest flag clear, a legitimate build option, so there
    is no digest to keep in step with the padding. `filler` varies the payload
    so two calls differ in nothing but their hash.
    """
    image = bytearray([filler] * MIN_FIRMWARE_BYTES)
    image[0] = IMAGE_MAGIC
    struct.pack_into("<H", image, CHIP_ID_OFFSET, 0x0009)
    struct.pack_into("<I", image, APP_DESC_OFFSET, APP_DESC_MAGIC)
    return bytes(image)


class RejectingFirmwareRepository(FakeFirmwareRepository):
    """Stands in for the unique (model, version) index rejecting an add."""

    def add(self, firmware: Firmware) -> Firmware:
        raise FirmwareAlreadyExists(firmware.model, firmware.version)


def repository_already_holding(data: bytes, model="ESP32", version="1.0.2"):
    """A repository whose rows already contain exactly these bytes."""
    sha256 = signing.calculate_sha256_bytes(data)
    return FakeFirmwareRepository(
        [
            Firmware(
                model=model,
                version=version,
                filename=f"{sha256}.bin",
                signature="s",
                sha256=sha256,
                size_bytes=len(data),
                id=1,
            )
        ]
    )


@pytest.fixture(scope="module")
def keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return private_key, private_pem


def test_execute_stores_data_under_its_content_hash(keypair):
    _, private_pem = keypair
    repo, storage = FakeFirmwareRepository(), FakeStorage()
    use_case = UploadFirmware(repo, storage, private_pem)
    data = valid_image()

    use_case.execute(
        UploadFirmwareRequest(
            model="ESP32",
            version="1.0.0",
            original_filename="firmware.bin",
            data=data,
        )
    )

    assert storage.files == {f"{signing.calculate_sha256_bytes(data)}.bin": data}


def test_execute_stores_nothing_when_the_version_is_malformed(keypair):
    """A `v` prefix used to upload cleanly and then never reach a single device.

    The field check runs before the image check because it is the cheaper of
    the two and neither depends on the other.
    """
    _, private_pem = keypair
    repo, storage = FakeFirmwareRepository(), FakeStorage()
    use_case = UploadFirmware(repo, storage, private_pem)

    with pytest.raises(signing.InvalidManifestField):
        use_case.execute(
            UploadFirmwareRequest(
                model="ESP32",
                version="v1.0.0",
                original_filename="firmware.bin",
                data=valid_image(),
            )
        )

    assert storage.files == {}
    assert repo.added == []


def test_two_uploads_in_the_same_second_do_not_overwrite_each_other(keypair):
    """The #29 case: distinct binaries, one model, no clock separating them.

    Under timestamp naming both landed on one file and the first row served the
    second's bytes, failing signature verification on-device forever.
    """
    _, private_pem = keypair
    repo, storage = FakeFirmwareRepository(), FakeStorage()
    use_case = UploadFirmware(repo, storage, private_pem)
    first, second = valid_image(0x11), valid_image(0x22)

    for version, data in (("1.0.0", first), ("1.0.1", second)):
        use_case.execute(
            UploadFirmwareRequest(
                model="ESP32",
                version=version,
                original_filename="main.ino.bin",
                data=data,
            )
        )

    assert len(storage.files) == 2
    for firmware, expected in zip(repo.added, (first, second), strict=True):
        assert storage.get(firmware.filename) == expected
        assert signing.calculate_sha256_bytes(storage.get(firmware.filename)) == firmware.sha256


def test_execute_records_firmware_with_matching_hash_and_verifiable_signature(keypair):
    private_key, private_pem = keypair
    repo, storage = FakeFirmwareRepository(), FakeStorage()
    use_case = UploadFirmware(repo, storage, private_pem)
    data = valid_image()

    firmware = use_case.execute(
        UploadFirmwareRequest(
            model="ESP32",
            version="1.0.0",
            original_filename="firmware.bin",
            data=data,
        )
    )

    assert firmware is repo.added[0]
    assert firmware.model == "ESP32"
    assert firmware.version == "1.0.0"
    assert firmware.sha256 == signing.calculate_sha256_bytes(data)
    assert firmware.filename == f"{firmware.sha256}.bin"
    assert firmware.original_filename == "firmware.bin"

    manifest_bytes = signing.build_manifest("ESP32", "1.0.0", firmware.sha256).encode("utf-8")
    private_key.public_key().verify(
        base64.b64decode(firmware.signature),
        manifest_bytes,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )


def test_execute_records_size_and_notes(keypair):
    _, private_pem = keypair
    repo, storage = FakeFirmwareRepository(), FakeStorage()
    use_case = UploadFirmware(repo, storage, private_pem)
    data = valid_image()

    firmware = use_case.execute(
        UploadFirmwareRequest(
            model="ESP32",
            version="1.0.0",
            original_filename="firmware.bin",
            data=data,
            notes="  Fix SNTP retry storm  ",
        )
    )

    assert firmware.size_bytes == len(data)
    assert firmware.notes == "Fix SNTP retry storm"


def test_execute_normalizes_blank_notes_to_none(keypair):
    _, private_pem = keypair
    repo, storage = FakeFirmwareRepository(), FakeStorage()
    use_case = UploadFirmware(repo, storage, private_pem)

    firmware = use_case.execute(
        UploadFirmwareRequest(
            model="ESP32",
            version="1.0.0",
            original_filename="firmware.bin",
            data=valid_image(),
            notes="   ",
        )
    )

    assert firmware.notes is None


def test_execute_records_no_notes_as_none(keypair):
    _, private_pem = keypair
    repo, storage = FakeFirmwareRepository(), FakeStorage()
    use_case = UploadFirmware(repo, storage, private_pem)

    firmware = use_case.execute(
        UploadFirmwareRequest(
            model="ESP32",
            version="1.0.0",
            original_filename="firmware.bin",
            data=valid_image(),
        )
    )

    assert firmware.notes is None


def test_execute_keeps_the_stored_blob_when_the_version_is_taken(keypair):
    """A content-addressed blob may already back another row, so it stays put.

    Deleting one a concurrent upload has committed a row against makes that row
    404, which reboot-loops every device mid-download.
    """
    _, private_pem = keypair
    repo, storage = RejectingFirmwareRepository(), FakeStorage()
    use_case = UploadFirmware(repo, storage, private_pem)
    data = valid_image()

    with pytest.raises(FirmwareAlreadyExists):
        use_case.execute(
            UploadFirmwareRequest(
                model="ESP32",
                version="1.0.0",
                original_filename="firmware.bin",
                data=data,
            )
        )

    assert storage.files == {f"{signing.calculate_sha256_bytes(data)}.bin": data}


def test_execute_stores_nothing_when_signing_fails():
    repo, storage = FakeFirmwareRepository(), FakeStorage()
    use_case = UploadFirmware(repo, storage, b"not a private key")

    with pytest.raises(ValueError):
        use_case.execute(
            UploadFirmwareRequest(
                model="ESP32",
                version="1.0.0",
                original_filename="firmware.bin",
                data=valid_image(),
            )
        )

    assert storage.files == {}
    assert repo.added == []


def test_execute_rejects_data_that_is_not_an_esp32_image(keypair):
    _, private_pem = keypair
    repo, storage = FakeFirmwareRepository(), FakeStorage()
    use_case = UploadFirmware(repo, storage, private_pem)

    with pytest.raises(InvalidFirmwareImage):
        use_case.execute(
            UploadFirmwareRequest(
                model="ESP32",
                version="1.0.0",
                original_filename="firmware.bin",
                data=b"not an image",
            )
        )

    assert storage.files == {}
    assert repo.added == []


def test_execute_rejects_a_binary_already_stored_under_another_version(keypair):
    _, private_pem = keypair
    data = valid_image()
    repo, storage = repository_already_holding(data), FakeStorage()
    use_case = UploadFirmware(repo, storage, private_pem)

    with pytest.raises(FirmwareBinaryAlreadyExists) as exc_info:
        use_case.execute(
            UploadFirmwareRequest(
                model="ESP32",
                version="1.0.3",
                original_filename="firmware.bin",
                data=data,
            )
        )

    assert exc_info.value.existing_version == "1.0.2"
    assert storage.files == {}
    assert repo.added == []
