#include <Arduino.h>
#include <M5Unified.h>
#include <ArduinoJson.h>
#include <esp_heap_caps.h>
#include <cstring>
#include "test_speech_wav.h"

static const size_t kRecSamples = 16000 * 2;
static const int kRecRate = 16000;
static const size_t kMaxWav = 512 * 1024;
static const uint32_t kRxTimeoutMs = 15000;
// M5Unified の setVolume は 0〜255。既定は 64。128 では録音再生が小さかった。
static const uint8_t kSpeakerVolume = 255;

static int16_t *rec_data = nullptr;
static uint8_t *wav_buf = nullptr;
static size_t wav_need = 0;
static size_t wav_got = 0;
static uint32_t wav_crc_expect = 0;
static int wav_id = 0;
static bool rx_binary = false;
static uint32_t rx_last_ms = 0;
static size_t prog_sent = 0;
// 8KB でも配送の往復が残った。受信バッファは 32768。
static const size_t kProgEvery = 16384;
static String line_acc;
static uint32_t touch_ms = 0;
static bool touch_down = false;
static int phase = 0;

static uint32_t crc32_ieee(const uint8_t *data, size_t len)
{
  uint32_t crc = 0xFFFFFFFFu;
  for (size_t i = 0; i < len; ++i)
  {
    crc ^= data[i];
    for (int b = 0; b < 8; ++b)
    {
      const uint32_t mask = (uint32_t)-(int32_t)(crc & 1u);
      crc = (crc >> 1) ^ (0xEDB88320u & mask);
    }
  }
  return crc ^ 0xFFFFFFFFu;
}

static void sendLine(const String &s)
{
  Serial.println(s);
}

static void show(const char *a, const char *b, const char *c)
{
  M5.Display.fillScreen(TFT_BLACK);
  M5.Display.setTextColor(TFT_WHITE, TFT_BLACK);
  M5.Display.setFont(&fonts::lgfxJapanGothicP_16);
  M5.Display.setTextDatum(top_left);
  M5.Display.drawString(a, 8, 16);
  M5.Display.drawString(b, 8, 56);
  M5.Display.drawString(c, 8, 96);
}

static void waitMicIdle()
{
  while (M5.Mic.isRecording())
  {
    M5.delay(1);
  }
}

static void speakerOn()
{
  waitMicIdle();
  M5.Mic.end();
  M5.delay(10);
  M5.Speaker.begin();
  M5.Speaker.setVolume(kSpeakerVolume);
}

static void speakerOff()
{
  while (M5.Speaker.isPlaying())
  {
    M5.delay(1);
  }
  M5.Speaker.end();
}

static void micOn()
{
  M5.Speaker.end();
  M5.delay(10);
  M5.Mic.begin();
}

static bool wavLooksOk(const uint8_t *data, size_t len)
{
  if (len < 44)
  {
    return false;
  }
  if (memcmp(data, "RIFF", 4) != 0 || memcmp(data + 8, "WAVEfmt ", 8) != 0)
  {
    return false;
  }
  return true;
}

struct WavFields
{
  uint32_t sample_rate;
  uint16_t channels;
  uint16_t bits;
  const uint8_t *pcm;
  size_t pcm_bytes;
  bool ok;
};

static WavFields parseWav(const uint8_t *data, size_t len)
{
  WavFields out = {};
  if (!wavLooksOk(data, len))
  {
    return out;
  }
  uint16_t audiofmt = 0;
  memcpy(&audiofmt, data + 20, 2);
  memcpy(&out.channels, data + 22, 2);
  memcpy(&out.sample_rate, data + 24, 4);
  memcpy(&out.bits, data + 34, 2);
  uint32_t fmt_size = 0;
  memcpy(&fmt_size, data + 16, 4);
  size_t pos = 12 + 8 + fmt_size;
  while (pos + 8 <= len)
  {
    char id[5] = {};
    memcpy(id, data + pos, 4);
    uint32_t csz = 0;
    memcpy(&csz, data + pos + 4, 4);
    if (memcmp(id, "data", 4) == 0)
    {
      if (pos + 8 + csz > len)
      {
        return out;
      }
      if (audiofmt != 1 || out.channels == 0 || out.channels > 2 || out.bits < 8 || out.bits > 16 || out.sample_rate == 0)
      {
        return out;
      }
      out.pcm = data + pos + 8;
      out.pcm_bytes = csz;
      out.ok = true;
      return out;
    }
    pos += 8 + csz;
  }
  return out;
}

static bool playRawFromWav(const uint8_t *data, size_t len)
{
  const WavFields w = parseWav(data, len);
  if (!w.ok || w.pcm == nullptr || w.pcm_bytes < 2)
  {
    return false;
  }
  static constexpr size_t kBufNum = 3;
  static constexpr size_t kBufSize = 1024;
  static uint8_t raw_buf[kBufNum][kBufSize];
  const bool stereo = w.channels > 1;
  const bool is16 = w.bits > 8;
  size_t remain = w.pcm_bytes;
  size_t off = 0;
  size_t idx = 0;
  while (remain > 0)
  {
    size_t n = remain < kBufSize ? remain : kBufSize;
    memcpy(raw_buf[idx], w.pcm + off, n);
    bool accepted;
    if (is16)
    {
      accepted = M5.Speaker.playRaw(reinterpret_cast<const int16_t *>(raw_buf[idx]), n / 2, w.sample_rate, stereo, 1, 0);
    }
    else
    {
      accepted = M5.Speaker.playRaw(raw_buf[idx], n, w.sample_rate, stereo, 1, 0);
    }
    if (!accepted)
    {
      return false;
    }
    off += n;
    remain -= n;
    idx = idx < (kBufNum - 1) ? idx + 1 : 0;
    M5.update();
  }
  return true;
}

static uint32_t waitPlaying(bool accepted)
{
  const uint32_t t0 = millis();
  while (accepted && M5.Speaker.isPlaying())
  {
    M5.update();
    M5.delay(1);
  }
  return millis() - t0;
}

static void playTone()
{
  speakerOn();
  const bool accepted = M5.Speaker.tone(880, 400);
  const uint32_t played_ms = waitPlaying(accepted);
  speakerOff();
  sendLine(String("{\"type\":\"SELF_TEST\",\"phase\":\"tone\",\"playWav\":") +
           (accepted ? "true" : "false") + ",\"played_ms\":" + String(played_ms) + "}");
  show("1 tone", accepted ? "played" : "tone false", "touch = rec 2s");
}

static void playRec()
{
  if (rec_data == nullptr)
  {
    sendLine("{\"type\":\"SELF_TEST\",\"phase\":\"recplay\",\"ok\":false,\"reason\":\"alloc\"}");
    return;
  }
  show("2 rec 2s", "speak now", "");
  waitMicIdle();
  micOn();
  size_t got = 0;
  const uint32_t t0 = millis();
  while (got + 200 <= kRecSamples && (millis() - t0) < 2500)
  {
    if (M5.Mic.record(rec_data + got, 200, kRecRate))
    {
      got += 200;
    }
    M5.update();
  }
  speakerOn();
  const bool accepted = M5.Speaker.playRaw(rec_data, got, kRecRate, false, 1, 0);
  const uint32_t played_ms = waitPlaying(accepted);
  speakerOff();
  sendLine(String("{\"type\":\"SELF_TEST\",\"phase\":\"recplay\",\"playWav\":") +
           (accepted ? "true" : "false") + ",\"samples\":" + String((unsigned)got) +
           ",\"played_ms\":" + String(played_ms) + "}");
  show("2 recplay", accepted ? "played" : "playRaw false", "touch = known WAV");
}

static bool playHeldWav(const uint8_t *data, size_t len, const char *phase_name, int sid)
{
  if (!wavLooksOk(data, len))
  {
    sendLine(String("{\"type\":\"SPEAK_ERROR\",\"id\":") + String(sid) + ",\"reason\":\"wav\"}");
    return false;
  }
  speakerOn();
  bool accepted = M5.Speaker.playWav(data, len);
  const char *path = "playWav";
  if (!accepted)
  {
    path = "playRaw";
    accepted = playRawFromWav(data, len);
  }
  const uint32_t played_ms = waitPlaying(accepted);
  speakerOff();
  if (accepted)
  {
    sendLine(String("{\"type\":\"SPEAK_FINISHED\",\"id\":") + String(sid) + ",\"played_ms\":" +
             String(played_ms) + "}");
  }
  else
  {
    sendLine(String("{\"type\":\"SPEAK_ERROR\",\"id\":") + String(sid) + ",\"reason\":\"playWav\"}");
  }
  sendLine(String("{\"type\":\"SELF_TEST\",\"phase\":\"") + phase_name + "\",\"playWav\":" +
           (strcmp(path, "playWav") == 0 && accepted ? "true" : "false") + ",\"path\":\"" + path +
           "\",\"accepted\":" + (accepted ? "true" : "false") + ",\"played_ms\":" + String(played_ms) +
           ",\"id\":" + String(sid) + "}");
  return accepted;
}

static void playKnownWav()
{
  show("3 known WAV", "playWav", "こんにちは");
  const bool ok = playHeldWav(test_speech_wav, test_speech_wav_len, "wav", 0);
  show("3 known WAV", ok ? "played" : "failed", "USB SPEAK_BEGIN ok");
}

static void abortBinary(const char *reason)
{
  const size_t got = wav_got;
  rx_binary = false;
  wav_need = 0;
  wav_got = 0;
  prog_sent = 0;
  sendLine(String("{\"type\":\"SPEAK_ERROR\",\"id\":") + String(wav_id) + ",\"reason\":\"" + reason +
           "\",\"got\":" + String((unsigned)got) + "}");
  show("USB error", reason, "JSON mode");
}

static void finishBinary()
{
  const uint32_t got_crc = crc32_ieee(wav_buf, wav_got);
  if (wav_got != wav_need)
  {
    abortBinary("short");
    return;
  }
  if (got_crc != wav_crc_expect)
  {
    abortBinary("crc");
    return;
  }
  sendLine(String("{\"type\":\"SPEAK_RECEIVED\",\"id\":") + String(wav_id) + ",\"bytes\":" +
           String((unsigned)wav_got) + ",\"crc32\":" + String(got_crc) + "}");
  rx_binary = false;
  const int sid = wav_id;
  const size_t n = wav_got;
  wav_need = 0;
  wav_got = 0;
  playHeldWav(wav_buf, n, "usb", sid);
  show("USB done", "touch = WAV again", "or SPEAK_BEGIN");
}

static void handleJsonLine(const String &line)
{
  JsonDocument doc;
  if (deserializeJson(doc, line))
  {
    return;
  }
  const char *type = doc["type"] | "";
  if (strcmp(type, "SPEAK_BEGIN") != 0)
  {
    return;
  }
  wav_id = doc["id"] | 0;
  const char *codec = doc["codec"] | "";
  const int nbytes = doc["bytes"] | 0;
  wav_crc_expect = doc["crc32"].as<uint32_t>();
  if (strcmp(codec, "wav") != 0 || nbytes <= 44 || (size_t)nbytes > kMaxWav || wav_buf == nullptr)
  {
    sendLine(String("{\"type\":\"SPEAK_ERROR\",\"id\":") + String(wav_id) + ",\"reason\":\"size\"}");
    return;
  }
  wav_need = (size_t)nbytes;
  wav_got = 0;
  prog_sent = 0;
  rx_binary = true;
  rx_last_ms = millis();
  sendLine(String("{\"type\":\"SPEAK_READY\",\"id\":") + String(wav_id) + "}");
  Serial.flush();
}

static void pollSerial()
{
  if (rx_binary)
  {
    for (;;)
    {
      const int avail = Serial.available();
      if (avail <= 0 || wav_got >= wav_need)
      {
        break;
      }
      size_t want = wav_need - wav_got;
      if ((size_t)avail < want)
      {
        want = (size_t)avail;
      }
      if (want > kProgEvery)
      {
        want = kProgEvery;
      }
      const int n = Serial.readBytes(wav_buf + wav_got, want);
      if (n <= 0)
      {
        break;
      }
      wav_got += (size_t)n;
      rx_last_ms = millis();
      if (wav_got < wav_need && (wav_got - prog_sent) >= kProgEvery)
      {
        prog_sent = wav_got;
        sendLine(String("{\"type\":\"SPEAK_PROGRESS\",\"id\":") + String(wav_id) + ",\"got\":" +
                 String((unsigned)wav_got) + "}");
      }
    }
    if (wav_got >= wav_need)
    {
      finishBinary();
      return;
    }
    if ((millis() - rx_last_ms) > kRxTimeoutMs)
    {
      abortBinary("timeout");
      return;
    }
    delay(1);
    return;
  }
  while (Serial.available() > 0)
  {
    const char c = (char)Serial.read();
    if (c == '\n')
    {
      handleJsonLine(line_acc);
      line_acc = "";
      if (rx_binary)
      {
        break;
      }
    }
    else if (line_acc.length() < 480)
    {
      line_acc += c;
    }
    else
    {
      line_acc = "";
    }
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
    if (!touch_down && (millis() - touch_ms) > 500)
    {
      touch_down = true;
      touch_ms = millis();
      if (rx_binary)
      {
        return;
      }
      if (phase == 0)
      {
        playRec();
        phase = 1;
      }
      else if (phase == 1)
      {
        playKnownWav();
        phase = 2;
      }
      else
      {
        playKnownWav();
      }
    }
  }
  else
  {
    touch_down = false;
  }
}

void setup()
{
  auto cfg = M5.config();
  M5.begin(cfg);
  Serial.setRxBufferSize(32768);
  Serial.begin(115200);
  Serial.setTimeout(20);
  M5.Display.setRotation(1);
  rec_data = (int16_t *)heap_caps_malloc(kRecSamples * sizeof(int16_t), MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
  wav_buf = (uint8_t *)heap_caps_malloc(kMaxWav, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
  if (rec_data == nullptr)
  {
    rec_data = (int16_t *)heap_caps_malloc(kRecSamples * sizeof(int16_t), MALLOC_CAP_8BIT);
  }
  if (wav_buf == nullptr)
  {
    wav_buf = (uint8_t *)heap_caps_malloc(kMaxWav, MALLOC_CAP_8BIT);
  }
  if (rec_data != nullptr)
  {
    memset(rec_data, 0, kRecSamples * sizeof(int16_t));
  }
  sendLine("{\"type\":\"SELF_TEST\",\"phase\":\"boot\"}");
  if (rec_data == nullptr || wav_buf == nullptr)
  {
    show("alloc fail", "PSRAM", "");
    sendLine("{\"type\":\"SELF_TEST\",\"phase\":\"alloc\",\"ok\":false}");
    return;
  }
  playTone();
  phase = 0;
}

void loop()
{
  if (rx_binary)
  {
    pollSerial();
    return;
  }
  M5.update();
  pollSerial();
  pollTouch();
  M5.delay(1);
}
