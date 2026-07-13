#include <WiFi.h>

#include "ota.h"

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

void setup() {
    Serial.begin(115200);

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

    // SNTP needs the network, so this runs only after WiFi connects, and
    // before markFirmwareValid()/loop() so every TLS handshake sees a real clock.
    if (!syncTimeSNTP()) {
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

    // If wifi connected then check the latest firmware
    if (WiFi.status() == WL_CONNECTED) {
        // If the version greater than esp32 version then ota
        if (check()) {
            int count = 0;
            while (!downloadFirmwareToFS()) {
                count++;
                if (count == 3) {
                    ESP.restart();
                }
            }
            OTA();  // Verifies the signature, flashes, and reboots into the new build
        }
    } else {
        // If cannot reconnect then restart esp32
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
