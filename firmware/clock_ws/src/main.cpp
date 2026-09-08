#include <Arduino.h>
#include <M5Unified.h>
#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include <mbedtls/base64.h>
#include <vector>
#include "config.h"

static WebSocketsClient ws;
static bool wifi_enabled = false;
static bool ws_connected = false;
static uint32_t last_host_ms = 0;
static const uint32_t kDisconnectAfterMs = 2500;

static String line0, line1, line2, line3;
static int line_count = 0;
enum UiKind
{
  UI_DISC,
  UI_CLOCK,
  UI_CHAT,
  UI_STATUS,
  UI_ALERT
};
static UiKind ui = UI_DISC;

static std::vector<uint8_t> speak_buf;
static bool listening = false;
static bool speaking = false;
static uint32_t silence_from_ms = 0;
static bool silence_timing = false;
static const int kSampleRate = 16000;
static const size_t kMicRead = 512;
static const int kSilenceAbs = 250;
static const uint32_t kSilenceMs = 3000;

static void sendText(const String &s)
{
  Serial.println(s);
  if (ws_connected)
  {
    String payload = s;
    ws.sendTXT(payload);
  }
}

static void drawDisconnected()
{
  ui = UI_DISC;
  M5.Display.fillScreen(TFT_BLACK);
  M5.Display.setTextDatum(middle_center);
  M5.Display.setTextColor(TFT_RED, TFT_BLACK);
  M5.Display.setFont(&fonts::lgfxJapanGothicP_24);
  M5.Display.drawString("未接続", M5.Display.width() / 2, M5.Display.height() / 2);
}

static void drawLines()
{
  M5.Display.fillScreen(TFT_BLACK);
  M5.Display.setTextDatum(middle_center);
  M5.Display.setTextColor(TFT_WHITE, TFT_BLACK);
  const int cx = M5.Display.width() / 2;
  const int cy = M5.Display.height() / 2;
  if (ui == UI_CHAT || ui == UI_STATUS)
  {
    M5.Display.setFont(&fonts::lgfxJapanGothicP_20);
    M5.Display.setTextDatum(top_center);
    if (line_count >= 1)
    {
      M5.Display.drawString(line0, cx, 24);
    }
    if (line_count >= 2)
    {
      M5.Display.drawString(line1, cx, 80);
    }
    if (line_count >= 3)
    {
      M5.Display.drawString(line2, cx, 136);
    }
    return;
  }
  M5.Display.setFont(&fonts::FreeSansBold18pt7b);
  if (ui == UI_ALERT)
  {
    M5.Display.setFont(&fonts::FreeSansBold12pt7b);
  }
  M5.Display.drawString(line0, cx, cy - 56);
  M5.Display.drawString(line1, cx, cy - 8);
  M5.Display.drawString(line2, cx, cy + 40);
  if (ui == UI_ALERT && line_count >= 4)
  {
    M5.Display.setFont(&fonts::lgfxJapanGothicP_20);
    M5.Display.drawString(line3, cx, cy + 84);
  }
}

static void noteHost()
{
  last_host_ms = millis();
}

static void stopMic()
{
  if (!listening)
  {
    return;
  }
  listening = false;
  silence_timing = false;
  M5.Mic.end();
  sendText("{\"type\":\"pcm_end\",\"reason\":\"stop\"}");
}

static void startMic()
{
  if (speaking)
  {
    return;
  }
  if (listening)
  {
    return;
  }
  M5.Speaker.end();
  auto cfg = M5.Mic.config();
  cfg.sample_rate = kSampleRate;
  M5.Mic.config(cfg);
  M5.Mic.begin();
  listening = true;
  silence_timing = false;
  sendText("{\"type\":\"pcm_start\"}");
}

static void startSpeaker()
{
  stopMic();
  speaking = true;
  speak_buf.clear();
  M5.Speaker.begin();
}

static void stopSpeaker()
{
  if (!speak_buf.empty())
  {
    const int16_t *samples = reinterpret_cast<const int16_t *>(speak_buf.data());
    const size_t n = speak_buf.size() / 2;
    M5.Speaker.playRaw(samples, n, kSampleRate, false, 1, 0);
  }
  uint32_t wait_from = millis();
  while (M5.Speaker.isPlaying() && (millis() - wait_from) < 15000)
  {
    delay(10);
  }
  M5.Speaker.stop();
  M5.Speaker.end();
  speak_buf.clear();
  speaking = false;
}

static String b64encode(const uint8_t *src, size_t len)
{
  size_t olen = 0;
  mbedtls_base64_encode(nullptr, 0, &olen, src, len);
  std::vector<unsigned char> dst(olen + 4);
  if (mbedtls_base64_encode(dst.data(), dst.size(), &olen, src, len) != 0)
  {
    return "";
  }
  return String(reinterpret_cast<char *>(dst.data()), olen);
}

static bool b64decode(const char *b64, std::vector<uint8_t> &out)
{
  size_t olen = 0;
  const size_t inlen = strlen(b64);
  mbedtls_base64_decode(nullptr, 0, &olen, reinterpret_cast<const unsigned char *>(b64), inlen);
  out.resize(olen);
  if (mbedtls_base64_decode(out.data(), out.size(), &olen, reinterpret_cast<const unsigned char *>(b64), inlen) != 0)
  {
    return false;
  }
  out.resize(olen);
  return true;
}

static void applyJson(const char *payload, size_t length = 0)
{
  JsonDocument doc;
  const DeserializationError err = (length > 0)
                                       ? deserializeJson(doc, payload, length)
                                       : deserializeJson(doc, payload);
  if (err)
  {
    return;
  }
  const char *type = doc["type"] | "";
  noteHost();

  if (strcmp(type, "hb") == 0)
  {
    return;
  }
  if (strcmp(type, "listen") == 0)
  {
    startMic();
    return;
  }
  if (strcmp(type, "idle") == 0)
  {
    stopMic();
    return;
  }
  if (strcmp(type, "speak_start") == 0)
  {
    startSpeaker();
    return;
  }
  if (strcmp(type, "speak_end") == 0)
  {
    stopSpeaker();
    sendText("SPEAK_DONE");
    return;
  }
  if (strcmp(type, "pcm") == 0)
  {
    const char *data = doc["data"] | "";
    std::vector<uint8_t> raw;
    if (!speaking)
    {
      startSpeaker();
    }
    if (b64decode(data, raw) && raw.size() >= 2)
    {
      speak_buf.insert(speak_buf.end(), raw.begin(), raw.end());
    }
    return;
  }

  JsonArray lines = doc["lines"].as<JsonArray>();
  if (strcmp(type, "clock") == 0 && !lines.isNull() && lines.size() >= 3)
  {
    line0 = lines[0].as<const char *>();
    line1 = lines[1].as<const char *>();
    line2 = lines[2].as<const char *>();
    line_count = 3;
    ui = UI_CLOCK;
    drawLines();
    Serial.println("CLOCK_APPLIED");
    return;
  }
  if (strcmp(type, "alert") == 0 && !lines.isNull() && lines.size() >= 4)
  {
    line0 = lines[0].as<const char *>();
    line1 = lines[1].as<const char *>();
    line2 = lines[2].as<const char *>();
    line3 = lines[3].as<const char *>();
    line_count = 4;
    ui = UI_ALERT;
    drawLines();
    return;
  }
  if (strcmp(type, "chat") == 0 && !lines.isNull() && lines.size() >= 1)
  {
    line0 = lines[0].as<const char *>();
    line1 = lines.size() > 1 ? lines[1].as<const char *>() : "";
    line2 = lines.size() > 2 ? lines[2].as<const char *>() : "";
    line_count = (int)lines.size();
    ui = UI_CHAT;
    drawLines();
    return;
  }
  if (strcmp(type, "status") == 0)
  {
    line0 = doc["text"] | "";
    line_count = 1;
    ui = UI_STATUS;
    drawLines();
  }
}

static void handleLine(String line)
{
  line.trim();
  if (line.isEmpty())
  {
    return;
  }
  applyJson(line.c_str());
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
    stopMic();
    drawDisconnected();
    break;
  case WStype_TEXT:
    applyJson(reinterpret_cast<const char *>(payload), length);
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
      if (buf.length() > 8192)
      {
        buf = "";
      }
    }
  }
}

static void pollMic()
{
  if (!listening || speaking)
  {
    return;
  }
  static int16_t mic_buf[kMicRead];
  if (!M5.Mic.isEnabled())
  {
    return;
  }
  if (!M5.Mic.record(mic_buf, kMicRead, kSampleRate))
  {
    return;
  }
  long acc = 0;
  for (size_t i = 0; i < kMicRead; ++i)
  {
    acc += abs(mic_buf[i]);
  }
  const long avg = acc / (long)kMicRead;
  if (avg < kSilenceAbs)
  {
    if (!silence_timing)
    {
      silence_timing = true;
      silence_from_ms = millis();
    }
    else if ((millis() - silence_from_ms) > kSilenceMs)
    {
      stopMic();
      return;
    }
  }
  else
  {
    silence_timing = false;
  }
  const String b64 = b64encode(reinterpret_cast<const uint8_t *>(mic_buf), kMicRead * 2);
  sendText(String("{\"type\":\"pcm\",\"data\":\"") + b64 + "\"}");
}

static void pollTouch()
{
  if (!M5.Touch.isEnabled())
  {
    return;
  }
  const auto &t = M5.Touch.getDetail(0);
  if (!t.wasClicked())
  {
    return;
  }
  sendText("{\"type\":\"touch\"}");
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
  pollTouch();
  pollMic();
  if (wifi_enabled)
  {
    ws.loop();
  }

  if (ui != UI_DISC && (millis() - last_host_ms) > kDisconnectAfterMs)
  {
    stopMic();
    drawDisconnected();
    Serial.println("CLOCK_TIMEOUT");
  }
  delay(5);
}
