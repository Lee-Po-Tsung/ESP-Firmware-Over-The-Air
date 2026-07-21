"""Signing, hashing and version-compare logic.

Signs the firmware manifest with RSA-PSS so an ESP32 can verify a download
against its embedded public key. The manifest format and PSS parameters must
stay in step with the on-device verifier in `esp32/main/ota.cpp`; changing
either means re-flashing every device.
"""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key


def calculate_sha256(filepath: str | Path) -> str:
    """Return the hex SHA-256 digest of a file, streamed in 4 KiB chunks."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def calculate_sha256_bytes(data: bytes) -> str:
    """Return the hex SHA-256 digest of an in-memory byte string."""
    return hashlib.sha256(data).hexdigest()


def build_manifest(model: str, version: str, sha256_hex: str) -> str:
    """The exact string the device re-builds and verifies: `model|version|sha256`."""
    return f"{model}|{version}|{sha256_hex}"


def sign_manifest(model: str, version: str, sha256_hex: str, private_key_pem: bytes) -> str:
    """Sign a manifest with RSA-PSS (MGF1-SHA256, max salt) and return base64.

    Matches the on-device verifier in `esp32/main/ota.cpp` which sets
    `MBEDTLS_RSA_PKCS_V21` with SHA-256.
    """
    manifest_bytes = build_manifest(model, version, sha256_hex).encode("utf-8")
    private_key = load_pem_private_key(private_key_pem, password=None)
    signature = private_key.sign(
        manifest_bytes,
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("utf-8")


def parse_version(version: str) -> tuple[int, ...]:
    """Parse a dotted version into a comparable tuple, mirroring the device.

    Matches parseVersionSegments/isVersionNewer in esp32/main/ota.cpp. At most
    three segments (so 1.2.3.4 truncates to 1.2.3 rather than differing from
    the device), and parsing stops at the first empty segment.

    A non-numeric or malformed segment becomes 0 instead of raising,
    so one bad record can't crash an update check.
    """
    segments: list[int] = []
    for part in version.split(".", 2):
        if not part:
            break
        digits = ""
        for ch in part:
            if not ch.isdigit():
                break
            digits += ch
        segments.append(int(digits) if digits else 0)
    return tuple(segments)


def compare_version(latest_v: str, current_v: str) -> bool:
    """Return True if `latest_v` is strictly newer than `current_v`."""
    return parse_version(latest_v) > parse_version(current_v)
