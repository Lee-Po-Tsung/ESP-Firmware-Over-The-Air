#pragma once
#include <Arduino.h>
#include <LittleFS.h>

// How long loop() waits before calling check() again. The device sends this
// with every check-in so the server can tell a late device from a dead one
// without keeping its own copy of the number to align by hand.
constexpr int POLL_INTERVAL_SECONDS = 6;

bool initFS();
void listDir(fs::FS& fs, const char* dirname, uint8_t levels);

bool initOTA(const String&, const String&);
bool initWiFi(const String&, const String&);
bool initWiFiEnterprise(const String&, const String&, const String&, const String&);
bool loadConfig(String& ssid, String& password, String& identity, String& username,
                bool& useEnterprise, String& serverUrl);
bool check();
bool downloadFirmwareToFS();
void OTA();
bool syncTimeSNTP();
void markFirmwareValid();
