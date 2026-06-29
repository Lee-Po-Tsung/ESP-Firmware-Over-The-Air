# Handoff & Context

Context for an agent picking up work on this project. It captures the current
state, the decisions made in planning, and why they were made, so you do not
have to re-litigate settled questions.

## Project goal

Turn the existing ESP32 secure-OTA prototype into a sellable, self-hostable
platform for managing firmware updates across a fleet of devices: a web
dashboard, user accounts, device and firmware management, and a path to
multi-tenancy later.

Team: one PM (owner) plus one collaborator who is new to coding. Both have AI
coding assistants. Plan accordingly: small well-scoped tasks, the PM owns the
security-critical path, the beginner gets low-risk high-learning work.

## Current state of the repo

A working Flask + ESP32 prototype already exists and does the hard part well.
Do not throw it away; port its proven logic forward.

What already works:

- `python/` — Flask server. Firmware upload (admin-key gated), `/api/check` and
  `/api/download` device endpoints, RSA-PSS signing of a `model|version|sha256`
  manifest, HTTPS with a self-signed cert.
- `esp32/main/` — device firmware. Downloads to LittleFS, verifies SHA-256 and
  the RSA-PSS signature before flashing, downgrade protection, A/B partition
  rollback via `esp_ota_mark_app_valid_cancel_rollback`, WPA2 Enterprise support,
  config loaded from `config.json` on LittleFS.

Security design is the strong point: the version number is signed into the
manifest, verification happens before flashing, TLS uses CA pinning. Keep this
intact when porting.

Known issues to fix during the port (M1):

- `python/configs.toml` is committed with a real `admin_key`, and the same key
  is printed in the README. Move it to `.env`, remove it from version control.
- `python/server.py` runs with `debug=True` on `host=0.0.0.0`. That exposes the
  Werkzeug debugger (remote code execution). Must be off; Flask's dev server is
  not for production anyway.
- `esp32/main/main.ino` hardcodes the system time (`tv.tv_sec = 1782283800`) to
  pass TLS cert validity checks. Replace with SNTP.
- Version compare is inconsistent: the server uses `split`, the device uses
  `sscanf`. Also `FIRMWARE_VERSION` in `ota.cpp` (2.1.0) is ahead of the latest
  in `version.json` (1.2.6). Align the logic and the version numbers.
- The device sends a hardcoded `"ID":"ESP32"` and never sends its computed MAC,
  so per-device tracking is impossible today. Address when device identity is
  needed.
- No tests anywhere.

## Decisions made in planning

These are settled. Do not re-open them without a reason.

- **MVP-first.** Ship the smallest sellable slice, defer everything else. The
  full vision lives in `MILESTONES.md`; the plan we build against is `ROADMAP.md`
  (M0 through M6). MVP is M0–M3, targeted at roughly two months part-time.
- **Reuse, do not rewrite.** Port the existing signing/verification logic to the
  new stack byte-for-byte so existing signatures still verify on-device.
- **SQLite + local files to start.** No Postgres, no MinIO yet. They add
  operational overhead with no payoff at this stage and would slow a beginner.
  SQLAlchemy abstracts the DB; a storage interface abstracts file storage. Swap
  later when a real need appears (M5/M6).
- **Pragmatic Clean Architecture.** The team will swap services later, so abstract
  the boundaries that actually change — persistence and blob storage — behind
  ports, and keep the crypto/domain logic free of any framework. Do not over-layer
  with full DTO mapping everywhere; that drowns a beginner in boilerplate. See the
  backend structure below.
- **Docker is not a dev requirement.** uv already gives reproducible Python envs.
  Docker Compose arrives only at the deployment milestone (M5), where it earns its
  keep bringing up the backend, a reverse proxy, and TLS.
- **Auth stays minimal at first.** JWT access token, bcrypt, two roles (Admin,
  Operator). Refresh-token rotation/revocation is deferred to M6.

## Proposed backend structure (pragmatic Clean Architecture)

Dependencies point inward: `api -> application -> domain`. `infrastructure`
implements the ports defined by the inner layers. Wiring is done with FastAPI's
`Depends()`. Only persistence and storage are abstracted behind ports; that is
what buys the swap-ability the team wants.

```
backend/
  domain/          # pure business logic, no framework imports
    models.py        # Firmware / Device entities (plain dataclasses)
    signing.py       # signing/verification ported from the Flask code
  ports/           # interfaces only (abstract method signatures)
    repository.py    # FirmwareRepository, DeviceRepository
    storage.py       # StorageBackend (put/get/delete one file)
  application/     # use cases that compose the ports
    upload_firmware.py
    check_update.py
  infrastructure/  # concrete, swappable implementations of the ports
    sqlite_repo.py   # SQLAlchemy implementation
    local_storage.py # local disk; add s3_storage.py later
  api/             # thin FastAPI layer
    routes.py
    deps.py          # dependency injection wiring
  main.py
```

The PM designs the ports and architecture (high leverage, costly if wrong). The
beginner fills in concrete adapters from a template — e.g. given `StorageBackend`
and `local_storage.py`, they write `s3_storage.py` the same way.

## Tooling decisions

- Python env: `uv`, locked with `uv.lock`. Always use uv, never bare pip.
- All three formatters for C/C++, Python & React, should run in pre-commit (local gate) and CI (PR gate).
  Not yet created — this is the next task.

## Time estimate (part-time, with AI assistance)

- M0: ~1 week
- M1: ~3 weeks (includes ESP32 hardware-in-the-loop testing, which AI does not
  speed up)
- M2: ~1 to 1.5 weeks
- M3: ~2 to 3 weeks
- MVP (M0–M3): roughly two months
- Through deployable product (M0–M5): roughly three months
- M6 (multi-tenancy, billing, etc.): not estimated; build only when a paying
  customer needs it

Reality check: AI speeds up writing greenfield code, not reviewing, debugging,
integrating, or hardware testing. Expect an overall speedup of 1.5 to 2x, not 5x.
The real bottleneck with a beginner is PM review bandwidth.
