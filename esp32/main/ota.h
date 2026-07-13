#pragma once
#include <Arduino.h>
#include <LittleFS.h>

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
