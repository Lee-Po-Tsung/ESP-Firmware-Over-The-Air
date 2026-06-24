# ESP-Firmware-Over-The-Air

ESP32 automatic firmware update with a secure HTTPS Flask server hosting the firmware files.

## Server-Side Setup

- Install Python dependencies using `uv`:
  ```bash
  uv sync
  ```
- Generate RSA key pairs for firmware signature signing:
  ```bash
  cd python
  openssl genrsa -out private_key.pem 2048
  openssl rsa -pubout -in private_key.pem -out public_key.pem
  cd ..
  ```
- Start the server once to automatically generate the self-signed SSL/TLS certificates:
  ```bash
  uv run server.py
  ```
  Terminate the server after certificates are created.

## Client-Side ESP32 Configuration

- Prepare the configuration structure in `data/config.json`:
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
- Package and upload the LittleFS filesystem partition matching the size limit of 1.25MB (`1310720` bytes):
  ```bash
  ~/.arduino15/packages/esp32/tools/mklittlefs/4.0.2-db0513a/mklittlefs -c data -p 256 -b 4096 -s 1310720 spiffs.bin
  ~/.arduino15/packages/esp32/tools/esptool_py/5.3.0/esptool --chip esp32s3 --port /dev/ttyACM0 --baud 921600 write_flash 0x2b0000 spiffs.bin
  ```
- Flash the initial application firmware with custom partitions enabled:
  ```bash
  arduino-cli compile --fqbn esp32:esp32:esp32s3 --board-options "PartitionScheme=custom,CDCOnBoot=cdc" --upload --port /dev/ttyACM0 esp32/main
  ```

## Publishing Firmware Updates

- Bump `FIRMWARE_VERSION` in `esp32/main/ota.cpp` (e.g., `1.2.6`).
- Build and export the new sketch binary:
  ```bash
  arduino-cli compile --fqbn esp32:esp32:esp32s3 --board-options "PartitionScheme=custom,CDCOnBoot=cdc" --output-dir build_out esp32/main
  ```
- Start the Flask server:
  ```bash
  uv run server.py
  ```
- Upload the binary to the server using the admin key defined in `configs.toml`:
  ```python
  import requests
  files = {'firmware': ('main.ino.bin', open('build_out/main.ino.bin', 'rb'))}
  data = {'model': 'ESP32', 'version': '1.2.6', 'admin_key': 'super_secret_admin_key'}
  requests.post('https://YOUR_SERVER_IP:8000/firmware/upload', files=files, data=data, verify=False)
  ```
