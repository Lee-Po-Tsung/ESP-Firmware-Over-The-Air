"""Shared test setup and the in-memory doubles for every port.

`infrastructure.db` creates its engine at import time from `get_settings()`,
which defaults to `backend/data/`. Point `DATA_DIR` at a throwaway directory
before any test module can trigger that import, so running the suite never
touches real application data. `JWT_SECRET` has no default in config on purpose,
so seed one here for the same reason, before config is ever imported. Same for
the signing key, which `main.py` reads at boot.

The fakes below subclass the abstract ports, which is what makes them useful:
a method added to a port turns every fake missing it into a TypeError at
construction. Duplicated per-module doubles cannot do that, and drifted.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="ota-test-data-"))
# 32+ bytes: config enforces RFC 7518's minimum HMAC key length for HS256.
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production-padded-to-length")


def _seed_signing_key() -> None:
    """Give the suite its own key pair rather than the developer's.

    Real keys live under `backend/keys/` and are git-ignored, so a checkout that
    has never run `scripts/generate_keys.py` has none. Tests that sign anything
    build their own pair; this exists for `main.py`, which reads the configured
    key at import.
    """
    keys_dir = Path(os.environ.setdefault("KEYS_DIR", tempfile.mkdtemp(prefix="ota-test-keys-")))
    keys_dir.mkdir(parents=True, exist_ok=True)
    private_key_path = keys_dir / "private_key.pem"
    if private_key_path.exists():
        return
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_key_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    (keys_dir / "public_key.pem").write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )


_seed_signing_key()


# Imported after the environment is seeded: config must not be read before the
# lines above have run.
from collections.abc import Iterable  # noqa: E402

from domain.models import Device, Firmware, User  # noqa: E402
from domain.signing import parse_version  # noqa: E402
from ports.repository import (  # noqa: E402
    DeviceRepository,
    FirmwareRepository,
    UserAlreadyExists,
    UserRepository,
)
from ports.storage import StorageBackend  # noqa: E402


class FakeFirmwareRepository(FirmwareRepository):
    """Rows in a list, queried the way the real repository queries them.

    Seeding rows rather than one lookup table per method means the answers
    cannot contradict each other, and a row written through `add` is visible to
    every read afterwards.
    """

    def __init__(self, rows: Iterable[Firmware] = ()) -> None:
        self.rows: list[Firmware] = list(rows)
        self.added: list[Firmware] = []

    def add(self, firmware: Firmware) -> Firmware:
        firmware.id = len(self.rows) + 1
        self.rows.append(firmware)
        self.added.append(firmware)
        return firmware

    def get_by_id(self, firmware_id: int) -> Firmware | None:
        return next((f for f in self.rows if f.id == firmware_id), None)

    def get_by_sha256(self, model: str, sha256: str) -> Firmware | None:
        return next((f for f in self.rows if f.model == model and f.sha256 == sha256), None)

    def get_latest_for_model(self, model: str) -> Firmware | None:
        candidates = [f for f in self.rows if f.model == model and f.active]
        if not candidates:
            return None
        return max(candidates, key=lambda f: (parse_version(f.version), f.id or 0))

    def deactivate(self, firmware_id: int) -> Firmware | None:
        firmware = self.get_by_id(firmware_id)
        if firmware is None:
            return None
        firmware.active = False
        return firmware

    def list_all(self) -> list[Firmware]:
        # Insertion order. Ordering is SQL's job and is covered against the real
        # repository, so imitating it here would only be a second claim about it
        # that nothing checks.
        return list(self.rows)


class FakeDeviceRepository(DeviceRepository):
    def __init__(self) -> None:
        self.devices: dict[str, Device] = {}

    def get_by_device_id(self, device_id: str) -> Device | None:
        return self.devices.get(device_id)

    def upsert(self, device: Device) -> Device:
        self.devices[device.device_id] = device
        return device

    def list_all(self) -> list[Device]:
        return list(self.devices.values())


class FakeUserRepository(UserRepository):
    def __init__(self) -> None:
        self.users: dict[str, User] = {}

    def add(self, user: User) -> User:
        if user.username in self.users:
            raise UserAlreadyExists(user.username)
        user.id = len(self.users) + 1
        self.users[user.username] = user
        return user

    def get_by_id(self, user_id: int) -> User | None:
        return next((u for u in self.users.values() if u.id == user_id), None)

    def get_by_username(self, username: str) -> User | None:
        return self.users.get(username)


class FakeStorage(StorageBackend):
    def __init__(self, files: dict[str, bytes] | None = None) -> None:
        self.files: dict[str, bytes] = files or {}

    def put(self, filename: str, data: bytes) -> None:
        self.files[filename] = data

    def get(self, filename: str) -> bytes:
        return self.files[filename]

    def delete(self, filename: str) -> None:
        self.files.pop(filename, None)

    def exists(self, filename: str) -> bool:
        return filename in self.files
