"""Generate the RSA key pair used to sign firmware manifests.

Writes a 2048-bit private key and its public key under `backend/keys/`, unless
they already exist. The public key is what you embed in each ESP32's config so
the device can verify what it downloads. Run once before starting the server:

    uv run python backend/scripts/generate_keys.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import get_settings  # noqa: E402
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402


def main() -> int:
    settings = get_settings()
    settings.keys_dir.mkdir(parents=True, exist_ok=True)

    if settings.private_key_path.exists() and settings.public_key_path.exists():
        print(f"Keys already exist in {settings.keys_dir}; nothing to do.")
        return 0

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    settings.private_key_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    settings.public_key_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    print(f"Wrote {settings.private_key_path}")
    print(f"Wrote {settings.public_key_path}")
    print("\nEmbed the public key in each device's config so it can verify firmware.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
