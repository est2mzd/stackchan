#include <Arduino.h>
#include <M5Unified.h>
#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include "config.h"

static WebSocketsClient ws;
static bool wifi_enabled = false;
static bool ws_connected = false;
static uint32_t last_clock_ms = 0;
static const uint32_t kDisconnectAfterMs = 2500;

static String line_date;
static String line_time;
static String line_weekday;
static bool have_clock = false;

static void drawDisconnected()
{
  M5.Display.fillScreen(TFT_BLACK);
  M5.Display.setTextDatum(middle_center);
  M5.Display.setTextColor(TFT_RED, TFT_BLACK);
  M5.Display.setFont(&fonts::lgfxJapanGothicP_24);
  M5.Display.drawString("未接続", M5.Display.width() / 2, M5.Display.height() / 2);
}

static void drawClock()
{
  M5.Display.fillScreen(TFT_BLACK);
  M5.Display.setTextDatum(middle_center);
  M5.Display.setTextColor(TFT_WHITE, TFT_BLACK);
  M5.Display.setFont(&fonts::FreeSansBold18pt7b);
  const int cx = M5.Display.width() / 2;
  const int cy = M5.Display.height() / 2;
  M5.Display.drawString(line_date, cx, cy - 48);
  M5.Display.drawString(line_time, cx, cy);
  M5.Display.drawString(line_weekday, cx, cy + 48);
}

static void applyClockJson(const char *payload, size_t length = 0)
{
  JsonDocument doc;
  const DeserializationError err = (length > 0)
                                       ? deserializeJson(doc, payload, length)
                                       : deserializeJson(doc, payload);
  if (err)
  {
    return;
  }
  if (strcmp(doc["type"] | "", "clock") != 0)
  {
    return;
  }
  JsonArray lines = doc["lines"].as<JsonArray>();
  if (lines.isNull() || lines.size() < 3)
  {
    return;
  }
  line_date = lines[0].as<const char *>();
  line_time = lines[1].as<const char *>();
  line_weekday = lines[2].as<const char *>();
  have_clock = true;
  last_clock_ms = millis();
  drawClock();
  Serial.println("CLOCK_APPLIED");
}

static void handleLine(String line)
{
  line.trim();
  if (line.isEmpty())
  {
    return;
  }
  applyClockJson(line.c_str());
}

static void wsEvent(WStype_t type, uint8_t *payload, size_t length)
{
  switch (type)
  {
  case WStype_CONNECTED:
    ws_connected = true;
    break;
  case WStype_DISCONNECTED:
    ws_connected = false;
    have_clock = false;
    drawDisconnected();
    break;
  case WStype_TEXT:
    applyClockJson(reinterpret_cast<const char *>(payload), length);
    break;
  default:
    break;
  }
}

static void pollSerial()
{
  static String buf;
  while (Serial.available() > 0)
  {
    const char c = static_cast<char>(Serial.read());
    if (c == '\n')
    {
      handleLine(buf);
      buf = "";
    }
    else if (c != '\r')
    {
      buf += c;
      if (buf.length() > 512)
      {
        buf = "";
      }
    }
  }
}

void setup()
{
  auto cfg = M5.config();
  M5.begin(cfg);
  Serial.begin(115200);
  Serial.println("CLOCK_FW_READY");
  M5.Display.setRotation(1);
  drawDisconnected();

  wifi_enabled = (strlen(WIFI_SSID_H) > 0);
  if (wifi_enabled)
  {
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID_H, WIFI_PASSWORD_H);
    ws.begin(SERVER_HOST_H, SERVER_PORT_H, SERVER_PATH_H);
    ws.onEvent(wsEvent);
    ws.setReconnectInterval(2000);
  }
}

void loop()
{
  M5.update();
  pollSerial();
  if (wifi_enabled)
  {
    ws.loop();
  }

  if (have_clock && (millis() - last_clock_ms) > kDisconnectAfterMs)
  {
    have_clock = false;
    drawDisconnected();
    Serial.println("CLOCK_TIMEOUT");
  }
  delay(10);
}
