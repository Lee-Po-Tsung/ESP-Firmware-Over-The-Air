from __future__ import annotations

import base64

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from domain.signing import (
    build_manifest,
    calculate_sha256,
    calculate_sha256_bytes,
    compare_version,
    sign_manifest,
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


def test_build_manifest_joins_with_pipes():
    assert build_manifest("ESP32", "1.0.1", "abcd") == "ESP32|1.0.1|abcd"


def test_calculate_sha256_matches_bytes_digest(tmp_path):
    data = b"firmware binary contents"
    filepath = tmp_path / "firmware.bin"
    filepath.write_bytes(data)

    assert calculate_sha256(filepath) == calculate_sha256_bytes(data)


def test_sign_manifest_produces_verifiable_signature(keypair):
    private_key, private_pem = keypair
    model, version, sha256_hex = "ESP32", "1.0.1", "a" * 64

    signature_b64 = sign_manifest(model, version, sha256_hex, private_pem)
    signature = base64.b64decode(signature_b64)

    manifest_bytes = build_manifest(model, version, sha256_hex).encode("utf-8")
    private_key.public_key().verify(
        signature,
        manifest_bytes,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )


def test_sign_manifest_rejects_tampered_manifest(keypair):
    private_key, private_pem = keypair
    signature_b64 = sign_manifest("ESP32", "1.0.1", "a" * 64, private_pem)
    signature = base64.b64decode(signature_b64)

    tampered = build_manifest("ESP32", "1.0.2", "a" * 64).encode("utf-8")
    with pytest.raises(InvalidSignature):
        private_key.public_key().verify(
            signature,
            tampered,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )


@pytest.mark.parametrize(
    "latest,current,expected",
    [
        ("1.0.1", "1.0.0", True),
        ("1.0.0", "1.0.1", False),
        ("1.0.0", "1.0.0", False),
        ("1.2.10", "1.2.9", True),
        ("2.0.0", "1.9.9", True),
        ("1.9.9", "2.0.0", False),
    ],
)
def test_compare_version(latest, current, expected):
    assert compare_version(latest, current) is expected


def test_compare_version_shorter_segment_list_is_not_newer():
    # split(".", 2) drops trailing segments beyond the third, so a shorter
    # dotted version is a tuple-prefix of a longer one and compares as older.
    assert compare_version("1.2", "1.2.0") is False
