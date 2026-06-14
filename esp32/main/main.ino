#include "LittleFSTest.h"
#include "ota.h" // have funcs about ota
#include <WiFi.h>

// global vars, ca&key in ota.cpp
const String ssid = "sumimi";
const String password = "Q9988551";
const String server_url = "https://leepotsung.pythonanywhere.com";
const String check_path = "/api/check";

// main
void setup() {
  Serial.begin(115200);
  delay(5000);                  // I open monitor. see debug msg
  pinMode(LED_BUILTIN, OUTPUT); // LED, for test ota

  initFS();
  initOTA(server_url, check_path);
  listDir(LittleFS, "/", 1);
  // WiFi
  if (!initWiFi(ssid, password)) {
    ESP.restart();
  }
}

void loop() {
  // digitalWrite(LED_BUILTIN, HIGH); // test code

  // if wifi connected then check the latest firmware
  if (WiFi.status() == WL_CONNECTED) {
    // if the version greater than esp32 version then ota
    if (check()) {
      int count = 0;
      while (!downloadFirmwareToFS()) {
        count++;
        if (count = 3) {
          ESP.restart();
        }
      }
      OTA();
    }
  } else {
    // if cannot reconnect then restart esp32
    if (!initWiFi(ssid, password))
      ESP.restart();
  }

  delay(6000); // every 6s, check version (temp

  // digitalWrite(LED_BUILTIN, LOW); // test code
}
