"""Data structures for the firmware and devices this server tracks.

`Firmware` is one uploaded build: which model and version it is for, the stored
file, and its hash and signature. `Device` is one ESP32 unit and the version it
last reported. Plain dataclasses, passed around by the rest of the backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class EventType(str, Enum):
    """What happened to a device, as recorded in the event log.

    `check` is a check-in worth keeping, `download` is a binary handed out,
    and `success` and `rollback` are read off a device's version changing
    between two check-ins. Stored as the string value.
    """

    CHECK = "check"
    DOWNLOAD = "download"
    SUCCESS = "success"
    ROLLBACK = "rollback"


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

    `size_bytes` and `notes` are dashboard display metadata and never enter the
    signed manifest, which stays `model|version|sha256`.

    `active` is the publish state. A withdrawn version keeps its row so the
    dashboard can show history, but `get_latest_for_model` never offers it.
    """

    model: str
    version: str
    filename: str
    signature: str
    sha256: str
    size_bytes: int
    notes: str | None = None
    active: bool = True
    original_filename: str | None = None
    id: int | None = None
    created_at: datetime | None = None


@dataclass
class Device:
    """A physical ESP32 unit in the field.

    Every field is what the device reported on its last check-in, so the
    dashboard always reads state that is at most one check interval old.
    Nothing here says whether the device is online or behind: both are read off
    `last_seen` and `current_version` at request time by `domain/fleet.py`,
    because a stored status would be wrong the moment a device stops reporting.

    `poll_interval_seconds` is how long the device intends to wait before
    checking in again. It travels with the check-in rather than being a server
    constant, so the one place that number is written down stays `ota.h`.

    Everything past `model` is nullable. Rows written before a field existed
    are never backfilled, since the device overwrites its own row on the next
    check-in anyway.
    """

    device_id: str
    model: str
    current_version: str | None = None
    last_seen: datetime | None = None
    poll_interval_seconds: int | None = None
    rssi: int | None = None
    ip: str | None = None
    last_error: str | None = None
    failed_attempts: int | None = None
    id: int | None = None


@dataclass
class DeviceEvent:
    """One entry in the append-only OTA history.

    Rows are never updated or deleted, so the log stays a record of what the
    fleet did rather than of what it looks like now. `Device` holds the current
    snapshot; this holds how it got there.

    `device_id` is the string the device reports, not a foreign key, so an event
    survives its device row and a download from an unregistered id still lands.
    `from_version` and `to_version` are both optional: a `download` knows only
    where it is going, and a first check-in knows only where it is.
    """

    device_id: str | None
    event_type: EventType
    from_version: str | None = None
    to_version: str | None = None
    id: int | None = None
    created_at: datetime | None = None
