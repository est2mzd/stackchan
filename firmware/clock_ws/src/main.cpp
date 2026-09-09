#include <Arduino.h>
#include <M5Unified.h>
#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include <esp_heap_caps.h>
#include <cstdio>
#include <cstring>
#include "config.h"

static WebSocketsClient ws;
static bool wifi_enabled = false;
static bool ws_connected = false;
static uint32_t last_host_ms = 0;
static const uint32_t kDisconnectAfterMs = 2500;

static String line0, line1, line2, line3;
static int line_count = 0;
static bool want_listen = false;
static bool play_active = false;
static bool speaker_up = false;
static uint32_t play_from_ms = 0;
enum UiKind
{
  UI_DISC,
  UI_CLOCK,
  UI_CHAT,
  UI_STATUS,
  UI_ALERT
};
static UiKind ui = UI_DISC;

static size_t pcm_expect = 0;
static size_t pcm_got = 0;
static uint32_t pcm_last_ms = 0;
static uint8_t *spk_store = nullptr;
static size_t spk_store_cap = 0;
static const size_t kPlayChunk = 1024;
static int16_t play_int[3][kPlayChunk];
static size_t play_off = 0;
static size_t play_nsamp = 0;
static int play_bi = 0;
static bool listening = false;
static bool speaking = false;
static bool heard_speech = false;
static uint32_t listen_from_ms = 0;
static uint32_t silence_from_ms = 0;
static bool silence_timing = false;
static const int kSampleRate = 16000;
static const uint32_t kSpkHwRate = 48000;
static const size_t kMicRead = 512;
static const int kSilenceAbs = 120;
static const uint32_t kSilenceMs = 600;
static const uint32_t kMaxListenMs = 4000;
static const size_t kMaxPcmSamples = kSampleRate * 5;
static int16_t *mic_store = nullptr;
static size_t mic_store_cap = 0;
static size_t mic_samples = 0;
static uint32_t listen_draw_ms = 0;
static uint32_t touch_sent_ms = 0;
static bool touch_down = false;
static bool touch_pending = false;

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
  M5.Display.setTextColor(TFT_WHITE, TFT_BLACK);
  if (ui == UI_CHAT || ui == UI_STATUS)
  {
    M5.Display.setFont(&fonts::lgfxJapanGothicP_16);
    M5.Display.setTextDatum(top_left);
    const int x = 8;
    const int ys[4] = {8, 56, 104, 152};
    const String *rows[4] = {&line0, &line1, &line2, &line3};
    const int n = line_count < 4 ? line_count : 4;
    for (int i = 0; i < n; ++i)
    {
      M5.Display.drawString(*rows[i], x, ys[i]);
    }
    return;
  }
  M5.Display.setTextDatum(middle_center);
  const int cx = M5.Display.width() / 2;
  const int cy = M5.Display.height() / 2;
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
    M5.Display.setFont(&fonts::lgfxJapanGothicP_16);
    M5.Display.drawString(line3, cx, cy + 84);
  }
}

static void noteHost()
{
  last_host_ms = millis();
}

static void stopSpeakerHardware()
{
  play_active = false;
  speaking = false;
  pcm_expect = 0;
  pcm_got = 0;
  play_off = 0;
  play_nsamp = 0;
  play_bi = 0;
  if (speaker_up)
  {
    M5.Speaker.stop();
    M5.Speaker.end();
    speaker_up = false;
  }
}

static void stopMicHardware()
{
  if (!listening)
  {
    return;
  }
  listening = false;
  silence_timing = false;
  M5.Mic.end();
}

static void sendPcmToHost()
{
  const size_t nbytes = mic_samples * 2;
  char hdr[72];
  snprintf(hdr, sizeof(hdr), "{\"type\":\"pcm_start\",\"bytes\":%u}", (unsigned)nbytes);
  sendText(hdr);
  if (mic_store != nullptr && nbytes > 0)
  {
    const uint8_t *p = reinterpret_cast<const uint8_t *>(mic_store);
    size_t left = nbytes;
    while (left > 0)
    {
      const size_t n = left > 1024 ? 1024 : left;
      Serial.write(p, n);
      p += n;
      left -= n;
    }
    Serial.flush();
  }
  sendText("{\"type\":\"pcm_end\",\"reason\":\"stop\"}");
}

static void stopMic()
{
  if (!listening)
  {
    return;
  }
  stopMicHardware();
  sendPcmToHost();
}

static void startMic()
{
  const bool was_speaking = speaking || speaker_up;
  stopSpeakerHardware();
  if (was_speaking)
  {
    delay(30);
  }
  if (listening)
  {
    return;
  }
  auto cfg = M5.Mic.config();
  cfg.sample_rate = kSampleRate;
  M5.Mic.config(cfg);
  M5.Mic.begin();
  listening = true;
  silence_timing = false;
  heard_speech = false;
  mic_samples = 0;
  listen_from_ms = millis();
  listen_draw_ms = 0;
}

static void finishPlay()
{
  stopSpeakerHardware();
  sendText("SPEAK_DONE");
  if (want_listen)
  {
    want_listen = false;
    startMic();
  }
}

static void startSpeaker()
{
  stopMicHardware();
  speaking = true;
  play_active = false;
  pcm_expect = 0;
  pcm_got = 0;
  play_off = 0;
  play_nsamp = 0;
  play_bi = 0;
  auto spk = M5.Speaker.config();
  spk.sample_rate = kSpkHwRate;
  spk.stereo = true;
  spk.task_priority = 5;
  M5.Speaker.config(spk);
  if (speaker_up)
  {
    M5.Speaker.end();
    speaker_up = false;
  }
  M5.Speaker.begin();
  speaker_up = true;
  M5.Speaker.setVolume(128);
  delay(50);
}

static void feedPlay()
{
  if (!speaker_up || spk_store == nullptr || play_off >= play_nsamp)
  {
    return;
  }
  const int16_t *src = reinterpret_cast<const int16_t *>(spk_store);
  while (play_off < play_nsamp)
  {
    const int ch = play_bi;
    if (M5.Speaker.isPlaying(ch))
    {
      return;
    }
    size_t n = play_nsamp - play_off;
    if (n > kPlayChunk)
    {
      n = kPlayChunk;
    }
    memcpy(play_int[ch], src + play_off, n * sizeof(int16_t));
    if (!M5.Speaker.playRaw(play_int[ch], n, kSampleRate, false, 1, ch, false))
    {
      return;
    }
    play_off += n;
    play_bi = (play_bi + 1) % 3;
    play_from_ms = millis();
  }
}

static void stopSpeaker()
{
  play_nsamp = pcm_got / 2;
  play_off = 0;
  play_bi = 0;
  if (play_nsamp < 2)
  {
    finishPlay();
    return;
  }
  play_active = true;
  speaking = true;
  feedPlay();
}

static void pollPlay()
{
  if (!play_active)
  {
    return;
  }
  feedPlay();
  if (play_off < play_nsamp)
  {
    return;
  }
  if ((millis() - play_from_ms) < 120)
  {
    return;
  }
  if (!M5.Speaker.isPlaying() || (millis() - play_from_ms) > 15000)
  {
    finishPlay();
  }
}

static void drawListenProgress()
{
  if ((millis() - listen_draw_ms) < 400 && listen_draw_ms != 0)
  {
    return;
  }
  listen_draw_ms = millis();
  const uint32_t elapsed = millis() - listen_from_ms;
  const uint32_t left_ms = (elapsed < kMaxListenMs) ? (kMaxListenMs - elapsed) : 0;
  line0 = "聞いています";
  line1 = String((left_ms + 999) / 1000) + " 秒";
  line2 = "";
  line3 = "";
  line_count = 2;
  ui = UI_STATUS;
  drawLines();
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
  if (mic_store == nullptr || mic_samples + kMicRead > mic_store_cap)
  {
    stopMic();
    return;
  }
  memcpy(mic_store + mic_samples, mic_buf, kMicRead * sizeof(int16_t));
  mic_samples += kMicRead;
  long acc = 0;
  for (size_t i = 0; i < kMicRead; ++i)
  {
    acc += abs(mic_buf[i]);
  }
  const long avg = acc / (long)kMicRead;
  drawListenProgress();
  if ((millis() - listen_from_ms) > kMaxListenMs)
  {
    stopMic();
    return;
  }
  if (avg < kSilenceAbs)
  {
    if (heard_speech)
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
  }
  else
  {
    heard_speech = true;
    silence_timing = false;
  }
}

static void pollTouch()
{
  if (!M5.Touch.isEnabled())
  {
    return;
  }
  const auto &t = M5.Touch.getDetail(0);
  if (t.isPressed())
  {
    if (!touch_down && (millis() - touch_sent_ms) > 500)
    {
      touch_down = true;
      touch_sent_ms = millis();
      if (pcm_expect > 0)
      {
        touch_pending = true;
      }
      else
      {
        sendText("{\"type\":\"touch\"}");
      }
    }
  }
  else
  {
    touch_down = false;
  }
  if (touch_pending && pcm_expect == 0)
  {
    touch_pending = false;
    sendText("{\"type\":\"touch\"}");
  }
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
    want_listen = speaking || play_active || (pcm_expect > 0);
    if (want_listen)
    {
      return;
    }
    startMic();
    return;
  }
  if (strcmp(type, "idle") == 0)
  {
    const bool was = speaking || play_active || (pcm_expect > 0) || speaker_up;
    want_listen = false;
    stopSpeakerHardware();
    stopMicHardware();
    if (was)
    {
      sendText("SPEAK_DONE");
    }
    return;
  }
  if (strcmp(type, "speak_start") == 0)
  {
    startSpeaker();
    const int n = doc["bytes"] | 0;
    if (n > 0 && spk_store != nullptr && (size_t)n <= spk_store_cap)
    {
      pcm_expect = (size_t)n;
      pcm_got = 0;
      pcm_last_ms = millis();
    }
    else
    {
      finishPlay();
    }
    return;
  }
  if (strcmp(type, "speak_end") == 0)
  {
    if (pcm_expect == 0 && !play_active)
    {
      stopSpeaker();
    }
    return;
  }
  if (strcmp(type, "pcm") == 0)
  {
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
    line3 = lines.size() > 3 ? lines[3].as<const char *>() : "";
    line_count = (int)lines.size();
    if (line_count > 4)
    {
      line_count = 4;
    }
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
  if (pcm_expect == 0)
  {
    while (Serial.available() > 0 && pcm_expect == 0)
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
        if (buf.length() > 16384)
        {
          buf = "";
        }
      }
    }
  }
  if (pcm_expect > 0)
  {
    if (spk_store != nullptr)
    {
      while (Serial.available() > 0 && pcm_got < pcm_expect)
      {
        const size_t room = pcm_expect - pcm_got;
        const int avail = Serial.available();
        const size_t n = (size_t)avail < room ? (size_t)avail : room;
        const int got = Serial.readBytes(spk_store + pcm_got, n);
        if (got <= 0)
        {
          break;
        }
        pcm_got += (size_t)got;
        pcm_last_ms = millis();
      }
    }
    noteHost();
    if (pcm_got >= pcm_expect)
    {
      pcm_expect = 0;
      stopSpeaker();
    }
    else if ((millis() - pcm_last_ms) > 2000)
    {
      pcm_expect = 0;
      stopSpeaker();
    }
  }
}

void setup()
{
  auto cfg = M5.config();
  M5.begin(cfg);
  Serial.begin(115200);
  Serial.setTimeout(20);
  mic_store_cap = kMaxPcmSamples;
  mic_store = static_cast<int16_t *>(
      heap_caps_malloc(mic_store_cap * sizeof(int16_t), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
  if (mic_store == nullptr)
  {
    mic_store_cap = kSampleRate * 2;
    mic_store = static_cast<int16_t *>(malloc(mic_store_cap * sizeof(int16_t)));
  }
  spk_store_cap = 320000;
  spk_store = static_cast<uint8_t *>(
      heap_caps_malloc(spk_store_cap, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
  if (spk_store == nullptr)
  {
    spk_store_cap = 64000;
    spk_store = static_cast<uint8_t *>(malloc(spk_store_cap));
  }
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
  pollPlay();
  pollMic();
  if (wifi_enabled)
  {
    ws.loop();
  }

  if (ui == UI_CLOCK && (millis() - last_host_ms) > kDisconnectAfterMs)
  {
    stopMic();
    drawDisconnected();
    Serial.println("CLOCK_TIMEOUT");
  }
  if (pcm_expect == 0 && !speaking)
  {
    delay(5);
  }
}
