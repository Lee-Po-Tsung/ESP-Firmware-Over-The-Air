#include <WiFi.h>
#include <sys/time.h>

#include "LittleFSTest.h"
#include "ota.h"  // have funcs about ota

#ifndef RGB_BUILTIN
#define RGB_BUILTIN 48
#endif

// Dynamic Wi-Fi & Server config variables loaded from LittleFS config.json on boot
String wifi_ssid;
String wifi_password;
String eap_identity;
String eap_username;
bool use_enterprise = false;
extern String server_url;
const String check_path = "/api/check";

// main
void setup() {
    Serial.begin(115200);
    delay(5000);  // I open monitor. see debug msg

    // Set system time to June 24, 2026 for TLS certificate validation
    struct timeval tv;
    tv.tv_sec = 1782283800;
    tv.tv_usec = 0;
    settimeofday(&tv, NULL);

    pinMode(LED_BUILTIN, OUTPUT);  // LED, for test ota

    // Initialize Filesystem first
    if (!initFS()) {
        Serial.println("Critical error: LittleFS initialization failed. Rebooting...");
        delay(1000);
        ESP.restart();
    }

    // Load configs dynamically
    if (!loadConfig(wifi_ssid, wifi_password, eap_identity, eap_username, use_enterprise,
                    server_url)) {
        Serial.println("[Config] Critical error: /config.json is missing or invalid! Halting...");
        while (true) {
            delay(1000);
        }
    }

    initOTA(server_url, check_path);
    listDir(LittleFS, "/", 1);

    // WiFi Connection
    bool connected = false;
    if (use_enterprise) {
        connected = initWiFiEnterprise(wifi_ssid, eap_identity, eap_username, wifi_password);
    } else {
        connected = initWiFi(wifi_ssid, wifi_password);
    }

    if (!connected) {
        ESP.restart();
    }

    markFirmwareValid();
}

void loop() {
    // Show this build's colour first, so it is visible before any OTA kicks in.
    // v1.0.0 = green, v1.0.1 = red. This line is the only per-version difference.
    Serial.println("LED: GREEN (running v1.0.0)");
    neopixelWrite(RGB_BUILTIN, 0, 64, 0);
    delay(6000);  // hold the colour, then re-check for an update

    // if wifi connected then check the latest firmware
    if (WiFi.status() == WL_CONNECTED) {
        // if the version greater than esp32 version then ota
        if (check()) {
            int count = 0;
            while (!downloadFirmwareToFS()) {
                count++;
                if (count == 3) {
                    ESP.restart();
                }
            }
            OTA();  // verifies the signature, flashes, and reboots into the new build
        }
    } else {
        // if cannot reconnect then restart esp32
        bool reconnected = false;
        if (use_enterprise) {
            reconnected = initWiFiEnterprise(wifi_ssid, eap_identity, eap_username, wifi_password);
        } else {
            reconnected = initWiFi(wifi_ssid, wifi_password);
        }
        if (!reconnected) {
            ESP.restart();
        }
    }
}
