#define FIRMWARE_VERSION "1.2.5"
// include http lib
#include <HTTPClient.h>
#include <NetworkClientSecure.h>
#include <WiFi.h>
// update lib
#include <FS.h>
#include <LittleFS.h>
#include <Update.h>

#include "LittleFSTest.h"

// gargs
const String ssid = "sumimi";
const String password = "Q9988551";
const String firmware_url = "https://leepotsung.pythonanywhere.com/firmware/latest";

const char* rootCACertificate = R"string_literal(
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

String md5;

// functions
void printProgress(size_t progress, size_t total) {
    float percentage = (progress / (float)total) * 100;
    Serial.printf("更新進度: %.2f%%\n", percentage);
}

bool initWiFi() {
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

bool checkFirmwareVersion(String url) {
    NetworkClientSecure* client = new NetworkClientSecure;
    client->setCACert(rootCACertificate);

    HTTPClient https;
    https.begin(*client, url);

    const char* headerKeys[] = {
        "Date", "Content-Type", "Content-Length", "Content-Disposition", "X-Version", "X-MD5"};
    size_t headerKeysCount = sizeof(headerKeys) / sizeof(headerKeys[0]);
    https.collectHeaders(headerKeys, headerKeysCount);

    int httpCode = https.sendRequest("HEAD");

    if (httpCode == HTTP_CODE_OK) {
        int headerCount = https.headers();
        for (int i = 0; i < headerCount; i++) {
            Serial.printf("%s: %s\n", https.headerName(i).c_str(), https.header(i).c_str());
        }
        md5 = https.header("X-MD5");
        String version = https.header("X-Version");

        Serial.println("Version: " + version);
        delete client;
        https.end();
        if (version == FIRMWARE_VERSION) {
            Serial.println("版本號相同不進行更新");
            return false;
        } else if (md5 == "") {
            Serial.println("缺少md5");
            return false;
        } else {
            return true;
        }
    } else {
        Serial.printf("HTTP error: %d\n", httpCode);
    }

    delete client;
    https.end();
    return false;
}

void doOTA(String url) {
    Serial.println("start update");
    NetworkClientSecure* client = new NetworkClientSecure;
    client->setCACert(rootCACertificate);

    HTTPClient https;
    https.begin(*client, url);

    int httpCode = https.GET();

    if (httpCode == HTTP_CODE_OK) {
        int contentLength = https.getSize();

        if (contentLength <= 0) {
            delete client;
            https.end();
            Serial.println("Invalid content length");
            return;
        }
        Update.onProgress(printProgress);
        if (!Update.begin(contentLength)) {
            delete client;
            https.end();
            Serial.println("Not enough space");
            return;
        }

        Update.setMD5(md5.c_str());

        WiFiClient* stream = https.getStreamPtr();
        size_t written = Update.writeStream(*stream);

        if (written == contentLength) {
            Serial.println("Written successfully");
        } else {
            Serial.println("Written failed");
        }

        if (Update.end()) {
            if (Update.isFinished()) {
                Serial.println("OTA Success");
                delete client;
                https.end();
                ESP.restart();
            } else {
                Serial.println("OTA not finished");
            }
        } else {
            Serial.printf("Update error: %s\n", Update.errorString());
        }
    } else {
        Serial.printf("HTTP error: %d\n", httpCode);
    }

    delete client;
    https.end();
}

// main
void setup() {
    Serial.begin(115200);
    delay(5000);
    pinMode(LED_BUILTIN, OUTPUT);

    if (!LittleFS.begin(true)) {
        Serial.println("LittleFS 掛載失敗");
        return;
    }
    listDir(LittleFS, "/", 3);

    if (!initWiFi()) {
        ESP.restart();
    }
}

void loop() {
    if (WiFi.status() == WL_CONNECTED) {
        if (checkFirmwareVersion(firmware_url)) {
            doOTA(firmware_url);
        }
    } else {
        if (!initWiFi()) {
            ESP.restart();
        }
    }
    // digitalWrite(LED_BUILTIN, HIGH);
    delay(6000);
    // digitalWrite(LED_BUILTIN, LOW);
}
