"""Interfaces for reading and writing firmware and device records.

Spells out the database operations the rest of the backend relies on, without
committing to a particular database. `infrastructure/sqlite_repo.py` provides
the SQLite implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from domain.models import Device, Firmware, User


class UserRepository(ABC):
    @abstractmethod
    def add(self, user: User) -> User:
        """Persist a new user and return it with its assigned id.

        Raises `UserAlreadyExists` if the username is taken.
        """

    @abstractmethod
    def get_by_id(self, user_id: int) -> User | None:
        """Return a user by primary key, or None."""

    @abstractmethod
    def get_by_username(self, username: str) -> User | None:
        """Return a user by username, or None."""


class UserAlreadyExists(Exception):
    """Raised when registering a username that already exists."""


class FirmwareAlreadyExists(Exception):
    """Raised when adding a firmware whose (model, version) is already stored."""


class FirmwareBinaryAlreadyExists(Exception):
    """Raised when the same binary is already stored for the model under another version.

    Carries the version it collided with, which is what the caller reports back.
    """

    def __init__(self, model: str, existing_version: str) -> None:
        super().__init__(model, existing_version)
        self.model = model
        self.existing_version = existing_version


class FirmwareRepository(ABC):
    @abstractmethod
    def add(self, firmware: Firmware) -> Firmware:
        """Persist a new firmware row and return it with its assigned id.

        Raises `FirmwareAlreadyExists` if that (model, version) is already stored.
        """

    @abstractmethod
    def get_by_id(self, firmware_id: int) -> Firmware | None:
        """Return a firmware by primary key, or None."""

    @abstractmethod
    def get_by_sha256(self, model: str, sha256: str) -> Firmware | None:
        """Return the firmware storing exactly these contents for the model, or None.

        Scoped per model, matching how (model, version) uniqueness is scoped:
        one binary serving two models is unusual but not an error.
        """

    @abstractmethod
    def get_latest_for_model(self, model: str) -> Firmware | None:
        """Return the newest firmware for a model, or None if none exist."""

    @abstractmethod
    def list_all(self) -> list[Firmware]:
        """Return every firmware, newest first (for the test/list page)."""


class DeviceRepository(ABC):
    @abstractmethod
    def get_by_device_id(self, device_id: str) -> Device | None:
        """Return a device by its hardware id, or None."""

    @abstractmethod
    def upsert(self, device: Device) -> Device:
        """Insert or update a device check-in record."""

    @abstractmethod
    def list_all(self) -> list[Device]:
        """Return every device, most recently seen first (for the device page)."""
