"""Data structures for the firmware and devices this server tracks.

`Firmware` is one uploaded build: which model and version it is for, the stored
file, and its hash and signature. `Device` is one ESP32 unit and the version it
last reported. Plain dataclasses, passed around by the rest of the backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Role(str, Enum):
    """Who is allowed to do what.

    `admin` publishes firmware and manages users; `operator` is a read-mostly
    account for the dashboard. Stored as its string value in the database.
    """

    ADMIN = "admin"
    OPERATOR = "operator"


@dataclass
class User:
    """A dashboard account. `password_hash` is a bcrypt hash, never the plaintext."""

    username: str
    password_hash: str
    role: Role = Role.OPERATOR
    id: int | None = None
    created_at: datetime | None = None


@dataclass
class Firmware:
    """A single firmware build for a given device model.

    `signature` is the base64-encoded RSA-PSS signature over the manifest
    `model|version|sha256` and must stay byte-for-byte compatible with what
    the ESP32 verifies on-device.

    `filename` is the storage key, `{sha256}.bin`, and carries no meaning
    beyond addressing the bytes. Because it is derived from the contents, one
    blob can back several rows, including rows for different models. Anything
    that removes firmware has to account for that. The name the uploader chose
    lives in `original_filename` and is for display only.
    """

    model: str
    version: str
    filename: str
    signature: str
    sha256: str
    original_filename: str | None = None
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
