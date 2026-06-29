"""Interface for storing and retrieving firmware binary files.

Four operations over a filename — put, get, delete, exists.
`infrastructure/local_storage.py` implements it against the local disk.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class StorageBackend(ABC):
    @abstractmethod
    def put(self, filename: str, data: bytes) -> None:
        """Store `data` under `filename`, overwriting any existing object."""

    @abstractmethod
    def get(self, filename: str) -> bytes:
        """Return the bytes stored under `filename`. Raises FileNotFoundError if absent."""

    @abstractmethod
    def delete(self, filename: str) -> None:
        """Remove `filename` if present; a no-op when it does not exist."""

    @abstractmethod
    def exists(self, filename: str) -> bool:
        """Return whether `filename` is present in the store."""
