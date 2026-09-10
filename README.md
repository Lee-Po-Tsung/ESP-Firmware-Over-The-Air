# ESP-Firmware-Over-The-Air

ESP32 automatic firmware update with a secure FastAPI Clean Architecture server hosting the firmware files.

See `CONTRIBUTING.md` for how work is tracked and how to get a change merged. The plan lives in the repository's GitHub milestones, one per stage, with the work itself in issues.

## Server-Side Setup

```bash
uv sync

# Generate the key pair you will sign firmware with (backend/keys/). This pair
# belongs to whoever publishes, not to the server: the server holds no private
# key and only verifies uploads against the public half on your account.
uv run python backend/scripts/generate_keys.py

# Generate a self-signed TLS cert for your LAN IP (backend/keys/).
# The device pins this cert as its CA, so the IP must match server_url in config.json.
uv run python backend/scripts/generate_tls_cert.py <your-lan-ip>

# Create the database schema
uv run alembic -c backend/alembic.ini upgrade head

# Configure secrets, then seed an account carrying that public key
cp backend/.env.example backend/.env   # set JWT_SECRET to a strong random value
uv run python backend/scripts/create_user.py --email you@example.com \
  --public-key backend/keys/public_key.pem
```

The SQLite database and firmware binaries live under `backend/data/`; your signing key pair and the TLS cert under `backend/keys/`. Both are git-ignored, as is `backend/.env`.

## Accounts and Auth

Sign up at `POST /api/auth/register` or from the dashboard, then log in at `POST /api/auth/login` (OAuth2 password form, so the address goes in the field the standard calls `username`) to get an access token and a refresh handle. Send the access token as `Authorization: Bearer <token>`; trade the handle at `POST /api/auth/refresh` when it expires, which rotates it. `scripts/create_user.py` still seeds accounts for a fresh install or CI.

There are no roles. An account sees the firmware it uploaded and the devices it registered, and nothing else, so a new account arrives at two empty lists. `/api/download` stays unauthenticated because the firmware has no credential to send: the link's random identifier is what guards it. `/api/check` is authenticated by the per-device secret rather than by an account.

Password reset works through `POST /api/auth/forgot-password` and `POST /api/auth/reset-password`. There is no mail transport configured, so the token is written to the server log for an operator to hand over.

### Run

```bash
uv run uvicorn main:app --app-dir backend --host 0.0.0.0 --reload \
  --ssl-keyfile backend/keys/tls_key.pem \
  --ssl-certfile backend/keys/tls_cert.pem
```

`--host 0.0.0.0` makes the server reachable from the device over the LAN; the default `127.0.0.1` only accepts local connections. The device dials the `https://` URL in its `config.json`, so the SSL flags are required.

## Frontend (Dashboard) Setup

```bash
cd frontend
npm install
cp .env.example .env.local   # set VITE_BACKEND to your running server's URL
npm run dev
```

The dev server proxies `/backend/*` to `VITE_BACKEND` (see `vite.config.ts`), so the backend above must already be running and reachable at that URL.

## Client-Side ESP32 Configuration

Prepare the configuration structure in `data/config.json`:

```json
{
  "wifi_ssid": "YOUR_WIFI_SSID",
  "wifi_password": "YOUR_WIFI_PASSWORD",
  "use_enterprise": false,
  "eap_identity": "",
  "eap_username": "",
  "server_url": "https://YOUR_SERVER_IP:8000",
  "device_id": "FROM_REGISTERING_THE_DEVICE",
  "device_secret": "FROM_REGISTERING_THE_DEVICE",
  "ca_cert": "-----BEGIN CERTIFICATE-----\nYOUR_CERT_PEM_CONTENT\n-----END CERTIFICATE-----\n",
  "public_key": "-----BEGIN PUBLIC KEY-----\nYOUR_PUBLIC_KEY_PEM_CONTENT\n-----END PUBLIC KEY-----\n"
}
```

Register the unit on the dashboard's device page first. It answers with a `device_id` and a `device_secret`, and the secret is shown exactly once: the server keeps only a hash of it. Both are per device, so each unit gets its own `config.json` and its own LittleFS image. A unit that is not registered, has the wrong secret, or has been disabled gets HTTP 401 from `/api/check` and `ota.cpp` says so on serial.

Package and upload the LittleFS filesystem partition matching the size limit of 1.25 MB (`1310720` bytes):

```bash
~/.arduino15/packages/esp32/tools/mklittlefs/4.0.2-db0513a/mklittlefs -c data -p 256 -b 4096 -s 1310720 spiffs.bin
~/.arduino15/packages/esp32/tools/esptool_py/5.3.0/esptool --chip esp32s3 --port /dev/ttyACM0 --baud 921600 write_flash 0x2b0000 spiffs.bin
```

Flash the initial application firmware with custom partitions enabled:

```bash
arduino-cli compile --fqbn esp32:esp32:esp32s3 --board-options "PartitionScheme=custom,CDCOnBoot=cdc" --upload --port /dev/ttyACM0 esp32/main
```

## Publishing Firmware Updates

- Bump `FIRMWARE_VERSION` in `esp32/main/ota.h`.
- Build and export the new sketch binary:
  ```bash
  arduino-cli compile --fqbn esp32:esp32:esp32s3 --board-options "PartitionScheme=custom,CDCOnBoot=cdc" --export-binaries esp32/main
  ```
- Sign it. The server verifies and never signs, so an unsigned upload is refused.
  ```bash
  uv run python backend/scripts/sign_firmware.py esp32/main/build/esp32.esp32.esp32s3/main.ino.bin
  ```
  It reads the model and version out of the image's build marker, hashes the exact
  bytes, and prints the signature.
- Upload the binary and that signature through the `frontend/` web app, or
  programmatically:
  ```python
  import requests
  base = 'https://YOUR_SERVER_IP:8000'
  token = requests.post(
      f'{base}/api/auth/login',
      data={'username': 'you@example.com', 'password': '...'},
  ).json()['access_token']
  image = 'esp32/main/build/esp32.esp32.esp32s3/main.ino.bin'
  requests.post(
      f'{base}/firmware/upload',
      files={'firmware': ('main.ino.bin', open(image, 'rb'))},
      data={'signature': 'PASTE_THE_SIGNATURE'},
      headers={'Authorization': f'Bearer {token}'},
  )
  ```
  The model and version are optional: the server reads them out of the image, and
  refuses a typed value that contradicts it.

## Scope Notes

- The dashboard keeps both tokens in `sessionStorage`, so a reload holds the session but closing the tab ends it. The access token expires after an hour and is renewed against the refresh handle, which is single-use and rotates on every renewal.
- Local dev serves HTTPS with the self-signed cert from `generate_tls_cert.py` (the device pins it as its CA). Production TLS via a reverse proxy with automatic certificates (Caddy) arrives at M5.
- The device secret sits in LittleFS in the clear, so dumping a unit's flash yields it. Making it genuinely secret needs flash encryption and Secure Boot v2, also M5. It only ever identifies a device; it cannot publish or withdraw anything.
- Password reset has no mail transport. The token is logged rather than sent.
