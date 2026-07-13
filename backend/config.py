"""Runtime configuration.

Reads every adjustable path and secret from environment variables, with
local-dev defaults. The SQLite database and uploaded firmware live under
`backend/data/`; the signing keys live under `backend/keys/` (create them with
`scripts/generate_keys.py`).
"""

from __future__ import annotations

import os
from functools import cached_property, lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Load a local `.env` (repo root or backend/) into the environment before any
# setting is read. Real values live there; the repo only ships `.env.example`.
load_dotenv(Path(__file__).resolve().parent / ".env")
load_dotenv()

BACKEND_DIR = Path(__file__).resolve().parent


def _require_env(name: str) -> str:
    """Read a mandatory secret from the environment, failing loudly if unset."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is not set. Copy backend/.env.example to backend/.env.")
    return value


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

        self.jwt_expires_minutes = int(os.environ.get("JWT_EXPIRES_MINUTES", "60"))

    @cached_property
    def jwt_secret(self) -> str:
        # No fallback secret on purpose: a hardcoded default is exactly the
        # shared-admin-key mistake M2 removes. Read lazily so key generation,
        # TLS certs and alembic run before .env exists; anything touching auth
        # still fails loudly. The server checks it at boot in main.py.
        return _require_env("JWT_SECRET")

    @property
    def database_url(self) -> str:
        return os.environ.get("DATABASE_URL", f"sqlite:///{self.db_path}")

    def read_private_key(self) -> bytes:
        return self.private_key_path.read_bytes()


@lru_cache
def get_settings() -> Settings:
    return Settings()
