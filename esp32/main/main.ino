// include http lib
#include <WiFi.h>
#include <HTTPClient.h>
// include sd card lib
#include <FS.h>
#include <SD.h>
#include <SPI.h>

// gargs
const char* ssid = "WiFi";
const char* password = "pass";

const char* url = "http://example.com/";

// functions
bool initSDCard() {
  Serial.print("init sd card ... ");
  
  if (!SD.begin(SD_CS_PIN)) {
    Serial.println("err");
    return false;
  }

  uint8_t cardType = SD.cardType();
  if (cardType == CARD_NONE) {
    Serial.println("err");
    return false;
  }

  Serial.printf("%llu MB\n", SD.cardSize() / (1024 * 1024));
  return true;
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

void downloadFileToSD(const char* url, const char* filepath) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("錯誤：Wi-Fi 未連線，無法下載。");
    return;
  }

  HTTPClient http;
  Serial.printf("正在請求網址: %s\n", url);
  
  http.begin(url);
  int httpCode = http.GET();

  if (httpCode == HTTP_CODE_OK) {
    int totalSize = http.getSize();
    Serial.printf("檔案大小: %d bytes\n", totalSize);

    File file = SD.open(filepath, FILE_WRITE);
    if (!file) {
      Serial.println("錯誤：無法在 SD 卡建立檔案，可能是沒有空間或防寫鎖定。");
      http.end();
      return;
    }

    WiFiClient* stream = http.getStreamPtr();
    uint8_t buff[2048] = { 0 }; 
    int downloadedSize = 0;

    Serial.println("開始下載並寫入 SD 卡...");
    while (http.connected() && (totalSize > 0 || totalSize == -1)) {
      size_t availableSize = stream->available();
      
      if (availableSize > 0) {
        int bytesToRead = (availableSize > sizeof(buff)) ? sizeof(buff) : availableSize;
        int bytesRead = stream->readBytes(buff, bytesToRead);
        file.write(buff, bytesRead);
        downloadedSize += bytesRead;
        if (totalSize > 0) {
          totalSize -= bytesRead;
        }
      }
      delay(1);
    }

    file.close();
    Serial.println();
    Serial.printf("下載完成！總共寫入: %d bytes\n", downloadedSize);

  } else {
    Serial.printf("下載失敗！HTTP 錯誤碼: %d\n", httpCode);
  }
  
  http.end();
}

// main
void setup() {
  Serial.begin(115200);
  initSDCard();
  initWiFi();
}

void loop() {
  
}
