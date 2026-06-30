# ESP-Firmware-Over-The-Air

ESP32 automatic firmware update with a secure FastAPI Clean Architecture server hosting the firmware files.

## Server-Side Setup

```bash
uv sync

# Generate the firmware-signing key pair (backend/keys/)
uv run python backend/scripts/generate_keys.py

# Generate a self-signed TLS cert for your LAN IP (backend/keys/).
# The device pins this cert as its CA, so the IP must match server_url in config.json.
uv run python backend/scripts/generate_tls_cert.py <your-lan-ip>

# Create the database schema
uv run alembic -c backend/alembic.ini upgrade head
```

The SQLite database and firmware binaries live under `backend/data/`; the keys under `backend/keys/`. Both are git-ignored.

### Run

```bash
uv run uvicorn main:app --app-dir backend --host 0.0.0.0 --reload \
  --ssl-keyfile backend/keys/tls_key.pem \
  --ssl-certfile backend/keys/tls_cert.pem
```

`--host 0.0.0.0` makes the server reachable from the device over the LAN; the default `127.0.0.1` only accepts local connections. The device dials the `https://` URL in its `config.json`, so the SSL flags are required.

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
  "ca_cert": "-----BEGIN CERTIFICATE-----\nYOUR_CERT_PEM_CONTENT\n-----END CERTIFICATE-----\n",
  "public_key": "-----BEGIN PUBLIC KEY-----\nYOUR_PUBLIC_KEY_PEM_CONTENT\n-----END PUBLIC KEY-----\n"
}
```

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

- Bump `FIRMWARE_VERSION` in `esp32/main/ota.cpp`.
- Build and export the new sketch binary:
  ```bash
  arduino-cli compile --fqbn esp32:esp32:esp32s3 --board-options "PartitionScheme=custom,CDCOnBoot=cdc" --output-dir build_out esp32/main
  ```
- Upload the binary via the web interface at `https://YOUR_SERVER_IP:8000/firmware`, or programmatically:
  ```python
  import requests
  files = {'firmware': ('main.ino.bin', open('build_out/main.ino.bin', 'rb'))}
  data = {'model': 'ESP32', 'version': '1.0.1', 'admin_key': 'super_secret_admin_key'}
  requests.post('https://YOUR_SERVER_IP:8000/firmware/upload', files=files, data=data)
  ```

## Scope Notes

- Real auth (replacing the shared admin key) lands in M2.
- Local dev serves HTTPS with the self-signed cert from `generate_tls_cert.py` (the device pins it as its CA). Production TLS via a reverse proxy with automatic certificates (Caddy) arrives at M5.
