#include "ota.h"
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <LittleFS.h>
#include <NetworkClient.h>
#include <NetworkClientSecure.h>
#include <Update.h>
#include <WiFi.h>

// rsa and sha256 ...
#include <mbedtls/base64.h>
#include <mbedtls/md.h>
#include <mbedtls/pk.h>
#include <mbedtls/sha256.h>

// ================= global vars =================
#define FIRMWARE_VERSION "1.2.5" // temp
uint64_t chipid = ESP.getEfuseMac();
String device_id = WiFi.macAddress();

NetworkClientSecure *client = nullptr;
// NetworkClient* client = nullptr;
String server_url;
String check_path;
String download_path;
String version;
String signature;

const char *rootCACertificate = R"string_literal(
-----BEGIN CERTIFICATE-----
MIIFazCCA1OgAwIBAgIRAIIQz7DSQONZRGPgu2OCiwAwDQYJKoZIhvcNAQELBQAw
TzELMAkGA1UEBhMCVVMxKTAnBgNVBAoTIEludGVybmV0IFNlY3VyaXR5IFJlc2Vh
cmNoIEdyb3VwMRUwEwYDVQQDEwxJU1JHIFJvb3QgWDEwHhcNMTUwNjA0MTEwNDM4
WhcNMzUwNjA0MTEwNDM4WjBPMQswCQYDVQQGEwJVUzEpMCcGA1UEChMgSW50ZXJu
ZXQgU2VjdXJpdHkgUmVzZWFyY2ggR3JvdXAxFTATBgNVBAMTDElTUkcgUm9vdCBY
MTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCCAgoCggIBAK3oJHP0FDfzm54rVygc
h77ct984kIxuPOZXoHj3dcKi/vVqbvYATyjb3miGbESTtrFj/RQSa78f0uoxmyF+
0TM8ukj13Xnfs7j/EvEhmkvBioZxaUpmZmyPfjxwv60pIgbz5MDmgK7iS4+3mX6U
A5/TR5d8mUgjU+g4rk8Kb4Mu0UlXjIB0ttov0DiNewNwIRt18jA8+o+u3dpjq+sW
T8KOEUt+zwvo/7V3LvSye0rgTBIlDHCNAymg4VMk7BPZ7hm/ELNKjD+Jo2FR3qyH
B5T0Y3HsLuJvW5iB4YlcNHlsdu87kGJ55tukmi8mxdAQ4Q7e2RCOFvu396j3x+UC
B5iPNgiV5+I3lg02dZ77DnKxHZu8A/lJBdiB3QW0KtZB6awBdpUKD9jf1b0SHzUv
KBds0pjBqAlkd25HN7rOrFleaJ1/ctaJxQZBKT5ZPt0m9STJEadao0xAH0ahmbWn
OlFuhjuefXKnEgV4We0+UXgVCwOPjdAvBbI+e0ocS3MFEvzG6uBQE3xDk3SzynTn
jh8BCNAw1FtxNrQHusEwMFxIt4I7mKZ9YIqioymCzLq9gwQbooMDQaHWBfEbwrbw
qHyGO0aoSCqI3Haadr8faqU9GY/rOPNk3sgrDQoo//fb4hVC1CLQJ13hef4Y53CI
rU7m2Ys6xt0nUW7/vGT1M0NPAgMBAAGjQjBAMA4GA1UdDwEB/wQEAwIBBjAPBgNV
HRMBAf8EBTADAQH/MB0GA1UdDgQWBBR5tFnme7bl5AFzgAiIyBpY9umbbjANBgkq
hkiG9w0BAQsFAAOCAgEAVR9YqbyyqFDQDLHYGmkgJykIrGF1XIpu+ILlaS/V9lZL
ubhzEFnTIZd+50xx+7LSYK05qAvqFyFWhfFQDlnrzuBZ6brJFe+GnY+EgPbk6ZGQ
3BebYhtF8GaV0nxvwuo77x/Py9auJ/GpsMiu/X1+mvoiBOv/2X/qkSsisRcOj/KK
NFtY2PwByVS5uCbMiogziUwthDyC3+6WVwW6LLv3xLfHTjuCvjHIInNzktHCgKQ5
ORAzI4JMPJ+GslWYHb4phowim57iaztXOoJwTdwJx4nLCgdNbOhdjsnvzqvHu7Ur
TkXWStAmzOVyyghqpZXjFaH3pO3JLF+l+/+sKAIuvtd7u+Nxe5AW0wdeRlN8NwdC
jNPElpzVmbUq4JUagEiuTDkHzsxHpFKVK7q4+63SM1N95R1NbdWhscdCb+ZAJzVc
oyi3B43njTOQ5yOf+1CceWxG1bQVs5ZufpsMljq4Ui0/1lvh+wjChP4kqKOJ2qxq
4RgqsahDYVvTH9w7jXbyLeiNdd8XM2w9U/t7y0Ff/9yi0GE44Za4rF2LN9d11TPA
mRGunUHBcnWEvgJBQl9nJEiU0Zsnvgc/ubhPgXRR4Xq37Z0j4r7g1SgEEzwxA57d
emyPxgcYxn/eR44/KJ4EBs+lVDR3veyJm+kXQ99b21/+jh5Xos1AnX5iItreGCc=
-----END CERTIFICATE-----
)string_literal";

const char *rsaPublicKey = R"string_literal(
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAxd3hZpdiuZoJ/48iBJ9F
3vX4RNo7eK7b1NlMfzezZRBCdB1vh/I32bG4sc+/npC3lmBRAs3TSW+GBne8fVIX
jmTZUz8eAO2mjtKZ0BD978rg1D5lUVRRSVEnL735O9aKRfXflG8C70r0YVVfIr1s
b4PreL34PlTZudTU42s/w1ixfAQdE4sElIFTDZpmhZGGBoGxa4b66U6Pd2rU1vR1
1xYfz1MDS3BCQT+HEgbSLumrG0ogvnwLwpp+EFbBp7Q2wEqZ9FYOacdX/YXJC4Uc
ml47jLm3KthS/pydYMTLvBBhUJyWhkHyLUgcCo9afwr1qrqenpzCFInngeFArFuN
8wIDAQAB
-----END PUBLIC KEY-----
)string_literal";

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
  if (mbedtls_pk_parse_public_key(&pk, (const unsigned char *)rsaPublicKey,
                                  strlen(rsaPublicKey) + 1) != 0) {
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
  client->setCACert(rootCACertificate);
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

// Execute the OTA update process, including verification and flashing
void OTA() {
  String fileSha256 = calculateFileSHA256("/firmware.bin");
  Serial.println("SHA-256: " + fileSha256);

  // Manifest String (same as server)
  String manifest = "ESP32|" + version + "|" + fileSha256;
  Serial.println(manifest);

  // compare RSA signature
  if (verifyManifestSignature(manifest, signature)) {
    Serial.println("Digital signature verification passed.");
  } else {
    Serial.println("Error: Digital signature verification failed.");
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
