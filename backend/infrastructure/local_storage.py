"""Stores firmware binaries as plain files in a local directory.

Implements the storage interface from `ports/storage.py`. Filenames are reduced
to their basename so an upload cannot write outside the configured directory.
"""

from __future__ import annotations

from pathlib import Path

from ports.storage import StorageBackend


class LocalStorage(StorageBackend):
    def __init__(self, base_dir: Path) -> None:
        self._base_dir = Path(base_dir)
        self._base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, filename: str) -> Path:
        # Guard against path traversal — store flat, by basename only.
        safe = Path(filename).name
        return self._base_dir / safe

    def put(self, filename: str, data: bytes) -> None:
        self._path(filename).write_bytes(data)

    def get(self, filename: str) -> bytes:
        return self._path(filename).read_bytes()

    def delete(self, filename: str) -> None:
        self._path(filename).unlink(missing_ok=True)

    def exists(self, filename: str) -> bool:
        return self._path(filename).exists()
