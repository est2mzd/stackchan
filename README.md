# StackChan（PC 頭脳）

公式スマホアプリは使わない。StackChan は入出力、PC（のち Jetson）が頭脳。

```
+---------------------------+     Wi-Fi（主）      +---------------------------+
| PC                        |     USB（予備）      | StackChan                 |
|                           |                      |                           |
|  中でやること             |  <--- マイクの音     |  中でやること             |
|    音声を文字にする       |                      |    マイクで録る           |
|    意図を分ける           |  ---> 返事の音声     |    スピーカーで鳴らす     |
|      会話 → LLM           |  ---> 画面の文字     |    液晶に出す             |
|      時計 → 日時          |                      |                           |
|      予定 → 読み上げ      |                      |                           |
+---------------------------+                      +---------------------------+
```

いま動くのは **フェーズ1の時計画面** と、フェーズ2〜4のホスト経路（マイク PCM、echo 会話、Calendar 判定）。Google OAuth と実スピーカ ACK は未確認。フェーズ5は未実装。

調査ログは `agent_reports/`。この README は手順だけ書く。

## 注意

- データ用 USB-C は **かかと側（ベース側）だけ**。両方に同時給電しない
- 運用の給電は USB 充電器。PC の USB だけでは足りないことが多い
- シリアルを開くと本体が再起動する。ポートは開いたまま使う
- ポート名は環境で変わる。先に `ls -l /dev/ttyACM*` で確認する
- Wi-Fi パスワードと API キーは git に入れない（`config.h` と `host/.env` は gitignore）

## 初期設定

かかと側を PC に繋ぐ。

```bash
python3 -m venv .venv
.venv/bin/pip install esptool pyserial websockets pytest platformio
```

シリアル権限（一度だけ）:

```bash
sudo cp tools/99-esp32s3-usbjtag.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=tty --subsystem-match=usb
```

ケーブルを抜き差ししてから:

```bash
lsusb | grep 303a:1001
ls -l /dev/ttyACM0
```

## フェーズ0 — 接続と公式ファームの退避

目的: 本体が見えること、公式イメージを手元に残して戻せるようにすること。

```bash
.venv/bin/esptool --port /dev/ttyACM0 flash-id
mkdir -p firmware/official
curl -L "https://m5burner-cdn.m5stack.com/firmware/746f9662f48ac465cccf49bcad941414.bin" \
  -o firmware/official/StackChan-UserDemo-V1.5.1.bin
sha256sum firmware/official/StackChan-UserDemo-V1.5.1.bin
```

期待する SHA256:

```
411578a2ebca2cfe3541fdc32aeddbc4703cf912a5daa7e1253f69306d6e1d87
```

公式へ戻す:

```bash
.venv/bin/esptool --port /dev/ttyACM0 write-flash 0x0 \
  firmware/official/StackChan-UserDemo-V1.5.1.bin
```

## フェーズ1 — 時計画面

目的: PC が 1 秒ごとに日時を送り、画面に日付・時刻・曜日を出す。切れると「未接続」。

USB だけで動かす（SSID は空のまま）:

```bash
cp firmware/clock_ws/include/config.template.h firmware/clock_ws/include/config.h
cd firmware/clock_ws
../../.venv/bin/pio run -e m5stack-cores3 -t upload --upload-port /dev/ttyACM0
cd ../..
.venv/bin/python host/clock_server.py --serial /dev/ttyACM0 --weekday en --tz Asia/Tokyo
```

画面例:

```
2026/09/08
22:58:33
Tuesday
```

日本語曜日は `--weekday ja`。ホストを止めると約 2.5 秒で「未接続」になる。

Wi-Fi にするとき（未確認）: `config.h` に 2.4GHz の SSID とパスワード、`SERVER_HOST_H` に PC の LAN IP を書き、再ビルドして焼く。本体は `ws://<PC_IP>:8000/ws/stackchan` に接続する。パスワードは README に書かない。

```bash
.venv/bin/python host/clock_server.py --weekday en --tz Asia/Tokyo
```

単体テスト:

```bash
.venv/bin/pytest -q host/test_clock_format.py
```

## フェーズ2 — 音声で時計モード

```bash
.venv/bin/python host/server.py --serial /dev/ttyACM0 --weekday en --asr whisper --tts none --llm echo
```

液晶に触れると時計と会話を切り替える。発話「時計モード」「会話モード」「戻って」でも切替。再生中は録音しない。

## フェーズ3 — 会話

```bash
.venv/bin/python host/server.py --serial /dev/ttyACM0 --asr whisper --tts edge --llm echo
```

ChatGPT: `OPENAI_API_KEY` を環境に出し `--llm openai`。Ollama: `--llm ollama --llm-base-url http://127.0.0.1:11434`。LLM は PC だけ。

## フェーズ4 — Google Calendar

`host/google_credentials.json`（gitignore）を置き、初回だけブラウザで OAuth する。トークンは `host/google_token.json`。

```bash
.venv/bin/python host/server.py --serial /dev/ttyACM0 --notify-minutes 10
```

credentials が無いあいだのデモ:

```bash
.venv/bin/python host/server.py --serial /dev/ttyACM0 --notify-minutes 1 \
  --calendar-demo-in-sec 70 --calendar-demo-title 定例 --asr none --tts none
```

## フェーズ5 — Jetson（未実装・任意）

予定: 同じホスト起動手順を Jetson で行う。インタフェースは変えない。
