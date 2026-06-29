"""Runtime configuration.

Reads every adjustable path and secret from environment variables, with
local-dev defaults. The SQLite database and uploaded firmware live under
`backend/data/`; the signing keys live under `backend/keys/` (create them with
`scripts/generate_keys.py`).
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent


class Settings:
    def __init__(self) -> None:
        self.data_dir = Path(os.environ.get("DATA_DIR", BACKEND_DIR / "data"))
        self.firmware_dir = Path(os.environ.get("FIRMWARE_DIR", self.data_dir / "firmware"))
        self.db_path = Path(os.environ.get("DB_PATH", self.data_dir / "app.db"))

        self.keys_dir = Path(os.environ.get("KEYS_DIR", BACKEND_DIR / "keys"))
        self.private_key_path = Path(
            os.environ.get("PRIVATE_KEY_PATH", self.keys_dir / "private_key.pem")
        )
        self.public_key_path = Path(
            os.environ.get("PUBLIC_KEY_PATH", self.keys_dir / "public_key.pem")
        )

        # Shared admin key gating uploads — replaced by real auth in M2.
        self.admin_key = os.environ.get("ADMIN_KEY", "super_secret_admin_key")

    @property
    def database_url(self) -> str:
        return os.environ.get("DATABASE_URL", f"sqlite:///{self.db_path}")

    def read_private_key(self) -> bytes:
        return self.private_key_path.read_bytes()


@lru_cache
def get_settings() -> Settings:
    return Settings()
