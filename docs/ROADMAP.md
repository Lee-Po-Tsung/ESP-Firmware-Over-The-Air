# Roadmap (MVP-first)

A trimmed plan for a two-person team where one person is new to coding. The
original `MILESTONES.md` stays as the long-term vision; this is the version we
actually build against.

Guiding rules for this plan:

- Ship a thin, sellable MVP first. Everything that can wait, waits.
- Reuse the proven crypto and OTA logic from the current Flask prototype. Do not
  rewrite signing or verification from scratch.
- Start on SQLite with files on local disk. Keep storage behind a small
  interface so we can swap to Postgres or S3/MinIO later without touching
  feature code.
- The PM owns the security-critical path (keys, signing, verification). The new
  collaborator works on low-risk, high-learning tasks first.
- Docker is not a dev requirement. It arrives only at the deployment milestone.

Each milestone marks tasks that are a good fit for the new collaborator with
**(good first task)**.

---

## ~~M0 — Ground Rules & Project Setup~~

**Title:** `M0 — Ground Rules & Project Setup`

**Description:**
Agree on how we work before writing feature code, so a beginner cannot easily
break things and review stays cheap.

- [x] Repo layout decided: `backend/`, `frontend/`, `esp32/`, shared `docs/`
- [x] Python env via `uv`, locked with `uv.lock`, setup documented in README
- [x] Formatters committed: `black` + `ruff` for Python, `clang-format` for
  [x] ++ (`prettier` + `eslint` deferred until M3 when the frontend starts)
- [x] Commit and branch policy in place: feature branch per change, small commits,
  [x] numbered or decorative comments, plain English
- [x] Pull request workflow: every change goes through a PR; main is protected
- [x] CI on every PR: `.github/workflows/lint.yml` runs black, ruff, and clang-format in check mode; failing PR cannot be merged
- [x] Pre-commit local gate (`.pre-commit-config.yaml`) mirrors CI
- `CONTRIBUTING.md` still to write **(good first task, M1 warm-up)**

**Done when:** A PR that fails lint or tests is blocked from merging, and both of
us can clone the repo and run the app from a documented setup.

---

## M1 — Core OTA Backend (In Progress - Backend completed, client-side fixes and tests pending)

**Title:** `M1 — Core OTA Backend`

**Description:**
Move today's working OTA flow onto the new stack with feature parity. No new
capabilities yet, just the same behaviour on FastAPI + SQLite.

**Backend layout (pragmatic Clean Architecture):**
Dependencies point inward: `api → application → domain`. `infrastructure`
implements the ports defined by the inner layers. Only persistence and storage
are abstracted behind ports — that is what buys swap-ability later without
drowning a beginner in boilerplate everywhere.

```
backend/
  domain/           # pure business logic, no framework imports
    models.py         # Firmware / Device entities (plain dataclasses)
    signing.py        # signing/verification ported from the Flask code
  ports/            # abstract interfaces only
    repository.py     # FirmwareRepository, DeviceRepository
    storage.py        # StorageBackend (put / get / delete one file)
  application/      # use cases that wire the ports together
    upload_firmware.py
    check_update.py
  infrastructure/   # concrete, swappable implementations of the ports
    sqlite_repo.py    # SQLAlchemy; swap for postgres_repo.py at M5 if needed
    local_storage.py  # local disk; add s3_storage.py later
  api/              # thin FastAPI layer — no business logic here
    routes.py
    deps.py           # dependency injection wiring via FastAPI Depends()
  main.py
```

The PM designs the ports and `domain/` (high leverage, costly if wrong). The
beginner fills in concrete adapters from a template — given `StorageBackend`
and `local_storage.py`, they write `s3_storage.py` the same way.

**Tasks:**
- [x] Scaffold the `backend/` tree above; wire FastAPI with SQLAlchemy and Alembic
- [x] Port the existing RSA-PSS signing and `model|version|sha256` manifest logic from the Flask code into `domain/signing.py`; keep it byte-for-byte compatible so existing signatures still verify on-device
- [x] Firmware model and an upload endpoint, gated by the existing admin key for now (real auth comes in M2)
- [x] Device endpoints `POST /api/check` and `GET /api/download/{id}` matching the current ESP32 protocol exactly
- [x] Local-filesystem `StorageBackend`; firmware binaries on disk, metadata in SQLite
- [ ] Fix the two known ESP32 issues while porting: replace the hardcoded system time with SNTP, and align the version-compare logic between device and server
- [ ] Write `CONTRIBUTING.md` as warm-up **(good first task)**
- [ ] Add unit tests for the signing and version-compare logic **(good first task)**

**Done when:** The existing ESP32 device can check, download, verify, and flash a
firmware update served by the new FastAPI backend. Same behaviour as today, new
stack.

---

## M2 — Auth & Roles (minimal)

**Title:** `M2 — Auth & Roles`

**Description:**
Replace the shared admin key with real accounts. Keep it simple; defer anything
fancy.

- User registration and login with bcrypt-hashed passwords
- JWT access token only for now; refresh-token rotation is deferred to M6
- Two roles: `Admin` and `Operator`
- Put the upload and delete endpoints behind admin auth; remove the shared admin
  key from the codebase and config
- Move every secret and hostname into `.env`; nothing hardcoded
- Write tests for the auth flow **(good first task)**

**Done when:** Only a logged-in admin can upload firmware, and the shared admin
key no longer exists anywhere in the repo.

---

## M3 — Minimal Dashboard (the sellable MVP)

**Title:** `M3 — Minimal Dashboard`

**Description:**
The smallest web UI someone would actually pay to use. Three screens, nothing
more.

- React with TypeScript and Vite, styled with shadcn/ui
- Login page; keep the JWT in memory, not localStorage
- Firmware page: list of versions per model, plus an upload form
- Device page: list of devices with current version and last-seen time
- Deliberately out of scope here: fleet charts, audit log, user management
- A Playwright end-to-end test for the upload flow **(good first task)**

**Done when:** An admin can log in, upload firmware, and see device status
entirely in the browser. This is the first demoable and sellable slice.

> Everything below this line is post-MVP. Do not start it until M3 ships and the
> core flow has been shown to a real user.

---

## M4 — Fleet Visibility

**Title:** `M4 — Fleet Visibility`

**Description:**
Turn raw check-ins into something an operator can read at a glance.

- Record OTA events (`check`, `download`, `success`, `rollback`) with timestamp,
  device, and from/to version
- Per-device version history timeline
- Fleet status view: how many devices per model are on the latest version vs
  behind
- Rollback detection: flag a device that checks in on a lower version than its
  last recorded one
- A summary metrics endpoint for the dashboard to read

**Done when:** An operator can see the live progress of a rollout and spot a
device that rolled back.

---

## M5 — Deployment & Productization

**Title:** `M5 — Deployment & Productization`

**Description:**
Make it shippable for a self-hosting customer. This is where Docker finally
arrives.

- Docker Compose bringing up the backend and a reverse proxy with automatic TLS
  (Caddy); upgrade SQLite to Postgres here only if a real need has appeared
- All configuration via `.env`; no hardcoded values anywhere
- API docs exposed at `/docs` with accurate descriptions and auth requirements
- A first-run setup wizard: create the admin, generate signing keys, register
  the first device, upload the first firmware
- An ESP32 provisioning guide for embedding the CA cert and public signing key
- `CHANGELOG.md` and semantic versioning for the platform itself

**Done when:** A new customer can deploy from scratch with Docker Compose,
finish onboarding, and push an update to an ESP32 within 30 minutes.

---

## M6 — Scale-ups (build only when a customer needs it)

**Title:** `M6 — Scale-ups`

**Description:**
The expensive, high-effort features from the original vision. None of these
should be built speculatively; pull an item out of here into a real milestone
only when demand is proven.

- Multi-tenancy: `org_id` scoping on every query, per-organization signing keys,
  member invitations, a superadmin role
- Refresh-token rotation and revocation
- Object storage: swap the storage interface to MinIO or S3
- Webhooks and email alerts on update success, failure, and rollback
- Billing via Stripe, or a license-key system for self-hosted installs

**Done when:** Deferred by design. Each line graduates into its own milestone
when a paying customer actually requires it.
