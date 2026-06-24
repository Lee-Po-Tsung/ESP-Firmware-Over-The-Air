#include "ota.h"
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <LittleFS.h>
#include <NetworkClient.h>
#include <NetworkClientSecure.h>
#include <Update.h>
#include <WiFi.h>
#include <esp_ota_ops.h>

// rsa and sha256 ...
#include <mbedtls/base64.h>
#include <mbedtls/md.h>
#include <mbedtls/pk.h>
#include <mbedtls/sha256.h>

// ================= global vars =================
#define FIRMWARE_VERSION "2.1.0" // temp
#define DEVICE_MODEL "ESP32"

uint64_t chipid = ESP.getEfuseMac();
String device_id = WiFi.macAddress();

NetworkClientSecure *client = nullptr;
// NetworkClient* client = nullptr;
String server_url;
String check_path;
String download_path;
String version;
String signature;

String rootCACertificate;
String rsaPublicKey;

// ================= internal func =================

// Calculate and print the update progress percentage
void printProgress(size_t progress, size_t total) {
  float percentage = (progress / (float)total) * 100;
  Serial.printf("Update progress: %.2f%%\n", percentage);
}

// Calculate the SHA-256 hash of a file stored in LittleFS
String calculateFileSHA256(const char *path) {
  File file = LittleFS.open(path, "r");
  if (!file)
    return "";
  Serial.println("load file and calculate sha256");

  mbedtls_sha256_context ctx;
  mbedtls_sha256_init(&ctx);
  mbedtls_sha256_starts(&ctx, 0); // 0: SHA-256

  uint8_t buf[1024];
  while (file.available()) {
    size_t len = file.read(buf, sizeof(buf));
    mbedtls_sha256_update(&ctx, buf, len);
  }
  file.close();

  uint8_t hash[32];
  mbedtls_sha256_finish(&ctx, hash);
  mbedtls_sha256_free(&ctx);

  String hex = "";
  for (int i = 0; i < 32; i++) {
    char c[3];
    sprintf(c, "%02x", hash[i]);
    hex += c;
  }
  return hex;
}

// Verify the RSA-PSS digital signature using the public key and manifest
bool verifyManifestSignature(String manifest, String b64Signature) {
  mbedtls_pk_context pk;
  mbedtls_pk_init(&pk);

  // load public key
  if (mbedtls_pk_parse_public_key(&pk, (const unsigned char *)rsaPublicKey.c_str(),
                                  rsaPublicKey.length() + 1) != 0) {
    Serial.println("Public key parsing failed!");
    return false;
  }

  // Base64 signature to string
  unsigned char sig[256];
  size_t sig_len = 0;
  mbedtls_base64_decode(sig, sizeof(sig), &sig_len,
                        (const unsigned char *)b64Signature.c_str(),
                        b64Signature.length());

  // compute manifest string sha256
  unsigned char hash[32];
  mbedtls_md_context_t md_ctx;
  mbedtls_md_init(&md_ctx);
  mbedtls_md_setup(&md_ctx, mbedtls_md_info_from_type(MBEDTLS_MD_SHA256), 0);
  mbedtls_md_starts(&md_ctx);
  mbedtls_md_update(&md_ctx, (const unsigned char *)manifest.c_str(),
                    manifest.length());
  mbedtls_md_finish(&md_ctx, hash);
  mbedtls_md_free(&md_ctx);

  // using padding.PSS mod
  mbedtls_rsa_context *rsa = mbedtls_pk_rsa(pk);
  mbedtls_rsa_set_padding(rsa, MBEDTLS_RSA_PKCS_V21, MBEDTLS_MD_SHA256);

  // verify signature
  int ret = mbedtls_pk_verify(&pk, MBEDTLS_MD_SHA256, hash, sizeof(hash), sig,
                              sig_len);
  mbedtls_pk_free(&pk);

  return (ret == 0);
}

// Initialize and configure the secure network client
void setClient() {
  client = new NetworkClientSecure();
  // client = new NetworkClient();
  client->setCACert(rootCACertificate.c_str());
}

// Delete the network client and free resources
void delClient() {
  delete client;
  client = nullptr;
}

// ================= external func =================

// Initialize OTA parameters with server URL and check path
bool initOTA(const String &serverUrl, const String &checkPath) {
  server_url = serverUrl;
  check_path = checkPath;
  return true;
}

// Connect to the specified WiFi network
bool initWiFi(const String &ssid, const String &password) {
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  int count = 0;
  while (WiFi.status() != WL_CONNECTED && count < 10) {
    delay(1000);
    Serial.print(".");
    ++count;
  }

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\nWiFi connect failed");
    return false;
  }
  Serial.println("\nWiFi connected");
  return true;
}

// Connect to WPA2 Enterprise WiFi network (e.g. PEAP)
bool initWiFiEnterprise(const String &ssid, const String &identity, const String &username, const String &password) {
  WiFi.disconnect(true);
  WiFi.mode(WIFI_STA);

  WiFi.begin(ssid.c_str(), WPA2_AUTH_PEAP, identity.c_str(), username.c_str(), password.c_str());

  int count = 0;
  while (WiFi.status() != WL_CONNECTED && count < 20) {
    delay(1000);
    Serial.print(".");
    ++count;
  }

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\nWiFi Enterprise connect failed");
    return false;
  }
  Serial.println("\nWiFi Enterprise connected");
  return true;
}

// Load OTA and Wi-Fi configurations from LittleFS JSON config
bool loadConfig(String &ssid, String &password, String &identity, String &username, bool &useEnterprise, String &serverUrl) {
  if (!LittleFS.exists("/config.json")) {
    Serial.println("Failed to find config file!");
    return false;
  }

  File file = LittleFS.open("/config.json", "r");
  if (!file) {
    Serial.println("Failed to open config file!");
    return false;
  }

  JsonDocument doc;
  DeserializationError error = deserializeJson(doc, file);
  file.close();

  if (error) {
    Serial.print("Failed to parse config file: ");
    Serial.println(error.c_str());
    return false;
  }

  ssid = doc["wifi_ssid"].as<String>();
  password = doc["wifi_password"].as<String>();
  identity = doc["eap_identity"].as<String>();
  username = doc["eap_username"].as<String>();
  useEnterprise = doc["use_enterprise"].as<bool>();
  serverUrl = doc["server_url"].as<String>();
  rootCACertificate = doc["ca_cert"].as<String>();
  rsaPublicKey = doc["public_key"].as<String>();

  if (ssid.isEmpty() || serverUrl.isEmpty() || rootCACertificate.isEmpty() || rsaPublicKey.isEmpty()) {
    Serial.println("Required config fields are missing or empty!");
    return false;
  }

  Serial.println("Config loaded successfully:");
  Serial.printf("SSID: %s\n", ssid.c_str());
  Serial.printf("Server URL: %s\n", serverUrl.c_str());
  Serial.printf("WPA2 Enterprise: %s\n", useEnterprise ? "Yes" : "No");
  return true;
}

// Check the server for an available firmware update
bool check() {
  Serial.println(FIRMWARE_VERSION);
  if (client == nullptr)
    setClient();

  HTTPClient https;
  String url = server_url + check_path;
  https.begin(*client, url);
  https.addHeader("Content-Type", "application/json");
  String data =
      "{\"ID\":\"ESP32\", \"version\":\"" + String(FIRMWARE_VERSION) + "\"}";
  Serial.println(data);
  int code = https.POST(data);
  if (code != HTTP_CODE_OK) {
    Serial.println("http connect error: " + String(code));
    https.end();
    delClient();
    return false;
  }

  String res = https.getString();
  JsonDocument doc;

  DeserializationError err = deserializeJson(doc, res);
  if (err) {
    Serial.print("json deserialize error: ");
    Serial.println(err.c_str());
    https.end();
    delClient();
    return false;
  }

  if (doc["update_available"] != true) {
    Serial.println("no new version");
    https.end();
    delClient();
    return false;
  }

  version = doc["version"].as<String>();
  signature = doc["signature"].as<String>();
  download_path = doc["download_url"].as<String>();

  https.end();
  return true;
}

// Download the firmware binary file to LittleFS
bool downloadFirmwareToFS() {
  HTTPClient https;
  String url = server_url + download_path;
  https.begin(*client, url);

  int code = https.GET();
  if (code != HTTP_CODE_OK) {
    Serial.println("http connect error: " + String(code));
    https.end();
    return false;
  }

  File file = LittleFS.open("/firmware.bin", "w");
  if (!file) {
    https.end();
    return false;
  }
  https.writeToStream(&file);
  file.close();

  https.end();
  delClient();
  return true;
}

// Check if v1 is newer than v2. Returns true if v1 > v2.
bool isVersionNewer(const String &v1, const String &v2) {
  int val1[3] = {0, 0, 0};
  int val2[3] = {0, 0, 0};
  sscanf(v1.c_str(), "%d.%d.%d", &val1[0], &val1[1], &val1[2]);
  sscanf(v2.c_str(), "%d.%d.%d", &val2[0], &val2[1], &val2[2]);
  for (int i = 0; i < 3; i++) {
    if (val1[i] > val2[i]) return true;
    if (val1[i] < val2[i]) return false;
  }
  return false;
}

// Mark firmware valid to cancel auto-rollback
void markFirmwareValid() {
  esp_err_t err = esp_ota_mark_app_valid_cancel_rollback();
  if (err == ESP_OK) {
    Serial.println("Firmware marked as valid (rollback canceled).");
  } else {
    Serial.printf("Failed to mark firmware as valid, error: 0x%x\n", err);
  }
}

// Execute the OTA update process, including verification and flashing
void OTA() {
  String fileSha256 = calculateFileSHA256("/firmware.bin");
  Serial.println("SHA-256: " + fileSha256);

  // Manifest String (same as server)
  String manifest = String(DEVICE_MODEL) + "|" + version + "|" + fileSha256;
  Serial.println(manifest);

  // compare RSA signature
  if (verifyManifestSignature(manifest, signature)) {
    Serial.println("Digital signature verification passed.");
  } else {
    Serial.println("Error: Digital signature verification failed.");
    LittleFS.remove("/firmware.bin");
    return;
  }

  // Downgrade protection / Freshness check
  if (!isVersionNewer(version, FIRMWARE_VERSION)) {
    Serial.printf("Error: Downgrade attack detected. Version %s is not newer than current %s.\n", version.c_str(), FIRMWARE_VERSION);
    LittleFS.remove("/firmware.bin");
    return;
  }

  // --- writing ---
  Serial.println("Writing to system partition...");
  File updateBin = LittleFS.open("/firmware.bin", "r");
  size_t updateSize = updateBin.size();

  if (Update.begin(updateSize)) {
    Update.writeStream(updateBin);
    if (Update.end()) {
      if (Update.isFinished()) {
        Serial.println("restart esp32...");
        updateBin.close();
        LittleFS.remove("/firmware.bin"); // clean
        delay(2000);
        ESP.restart();
      } else {
        Serial.println("err");
      }
    } else {
      Serial.printf("Error: Write failed: %s\n", Update.errorString());
    }
  } else {
    Serial.println("Not enough space");
  }
  updateBin.close();
}
