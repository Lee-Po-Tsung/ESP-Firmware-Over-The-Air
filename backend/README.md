# OTA Backend (M1)

FastAPI + SQLAlchemy + Alembic server for signing, listing and serving ESP32
firmware updates. Organised as pragmatic Clean Architecture.

## Layout

```
backend/
  domain/           # core data + rules, no framework imports
    models.py         # Firmware / Device dataclasses
    signing.py        # RSA-PSS signing, sha256, version-compare
  ports/            # interfaces the rest of the code depends on
    repository.py     # firmware / device read-write contract
    storage.py        # firmware binary store contract
  application/      # the actual operations
    upload_firmware.py
    check_update.py
  infrastructure/   # concrete implementations
    db.py             # SQLAlchemy engine, session, tables
    sqlite_repo.py    # repository on SQLite
    local_storage.py  # firmware binaries on local disk
  api/              # HTTP layer
    routes.py
    deps.py           # builds dependencies via FastAPI Depends()
  alembic/          # database migrations
  scripts/
    generate_keys.py  # create the signing key pair
  config.py
  main.py
```

## First-time setup

From the repo root:

```bash
uv sync

# 1. Generate the firmware-signing key pair (backend/keys/)
uv run python backend/scripts/generate_keys.py

# 2. Create the database schema
uv run alembic -c backend/alembic.ini upgrade head
```

The database starts empty — upload firmware through the web page once the server
is running.

The SQLite database and firmware binaries live under `backend/data/`; the keys
under `backend/keys/`. Both are git-ignored.

## Run

```bash
uv run uvicorn main:app --app-dir backend --reload
```

Endpoints:

- `POST /api/check` — body `{"ID": "<model>", "version": "<x.y.z>"}` (device protocol)
- `GET  /api/download/{id}` — firmware binary
- `GET  /firmware` — web page: firmware list + admin-key upload form
- `GET  /docs` — OpenAPI UI

Uploading a firmware computes its SHA-256 and signs the manifest
`model|version|sha256` with the private key. A device on an older version then
sees the update via `/api/check`, downloads it, and verifies the signature with
the embedded public key.

## Configuration

`config.py` reads everything from env vars with local-dev defaults:

| Var | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `sqlite:///backend/data/app.db` | database connection |
| `FIRMWARE_DIR` | `backend/data/firmware` | binary storage |
| `KEYS_DIR` | `backend/keys` | signing key pair location |
| `ADMIN_KEY` | `super_secret_admin_key` | shared upload gate (removed in M2) |

## Scope notes

- ESP32-side M1 items (SNTP clock, device/server version-compare alignment) are
  not part of this change — backend only.
- Real auth (replacing the shared admin key) lands in M2.
- TLS is not wired up here; run over plain HTTP locally. Automatic TLS arrives
  at M5 (Caddy).
```
