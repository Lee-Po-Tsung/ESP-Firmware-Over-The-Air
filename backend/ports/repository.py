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


class FirmwareRepository(ABC):
    @abstractmethod
    def add(self, firmware: Firmware) -> Firmware:
        """Persist a new firmware row and return it with its assigned id."""

    @abstractmethod
    def get_by_id(self, firmware_id: int) -> Firmware | None:
        """Return a firmware by primary key, or None."""

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
