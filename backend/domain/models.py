"""Data structures for the firmware and devices this server tracks.

`Firmware` is one uploaded build: which model and version it is for, the stored
file, and its hash and signature. `Device` is one ESP32 unit and the version it
last reported. Plain dataclasses, passed around by the rest of the backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Firmware:
    """A single firmware build for a given device model.

    `signature` is the base64-encoded RSA-PSS signature over the manifest
    `model|version|sha256` and must stay byte-for-byte compatible with what
    the ESP32 verifies on-device.
    """

    model: str
    version: str
    filename: str
    signature: str
    sha256: str
    id: int | None = None
    created_at: datetime | None = None


@dataclass
class Device:
    """A physical ESP32 unit in the field.

    Kept intentionally small for M1 — only enough to model the check-in. Fleet
    visibility (last-seen, history, rollback detection) arrives in M4.
    """

    device_id: str
    model: str
    current_version: str | None = None
    last_seen: datetime | None = None
    id: int | None = None
