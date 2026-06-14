#pragma once
#include <Arduino.h>

bool initOTA(const String &, const String &);
bool initWiFi(const String &, const String &);
bool check();
bool downloadFirmwareToFS();
void OTA();
