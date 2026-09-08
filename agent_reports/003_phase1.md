# フェーズ1 実施報告

実施日: 2026-09-08  
入力: `user_directions/001_objective.md`、`agent_reports/001_plan.md`、`agent_reports/002_phase0.md`  
作業ディレクトリ: `/home/takuya/work/stackchan`  
生ログ: `agent_reports/phase1_artifacts/`  
ポート名 `/dev/ttyACM0` は環境で変わる。

---

## 背景

計画のフェーズ1は、会話（LLM）を入れず、ホスト接続と時計画面だけを通す。完了条件は次である。

- 本体が PC の WebSocket に接続する
- ホストが 1 秒ごとに日時を送り、画面に `YYYY/MM/DD` / `HH:MM:SS` / 曜日 を出す
- 曜日は設定で日本語にも切替可能（初期は英語）
- 切断時は本体側に「未接続」と出す

フェーズ0では土台に [74th/websocket-control-stackchan](https://github.com/74th/websocket-control-stackchan) を選んだ。ただしそのファームは Wi-Fi SSID/パスワードがビルド時必須で、フェーズ0では未設定のまま公式 1.5.1 を消さなかった。フェーズ1でプロトコルを読み、時計を画面に出せるかを確定する。

Wi-Fi パスワードは本レポートに書かない。SSID だけ記録する。

---

## 目的

1. 74th の WebSocket プロトコルで日付・時刻・曜日の3行を描けるか判定する
2. ホストが 1Hz で時計 JSON を送れるようにする（曜日は `en` / `ja`）
3. 本体画面にその3行を出し、2.5 秒以上届かなければ「未接続」にする
4. 実機で確認する。WebSocket が使えなければ USB シリアルで同等を通す

---

## 結論

74th は GitHub ユーザ名で、リポジトリは [74th/websocket-control-stackchan](https://github.com/74th/websocket-control-stackchan)（コミュニティ製。「本体＝I/O、PC＝頭脳」）。protobuf には音声・状態・サーボだけで、時計や任意テキストを描くメッセージが無い。画面は状態バー（Idle / Disconnected など）と顔だけである。フェーズ1の時計画面には使えない。

代わりに専用ファーム `firmware/clock_ws/` と Python ホスト `host/clock_server.py` を入れ、公式 1.5.1 の上に焼いた。USB シリアル（115200）で実機確認した。起動後に `CLOCK_FW_READY`、受信後に `CLOCK_APPLIED`、2.5 秒無通信で `CLOCK_TIMEOUT`（画面は「未接続」）をシリアルで受け取った。書き込み後もホストを 1Hz で動かしている。

曜日切替はホストの `--weekday en|ja`。単体テストで英語 `Tuesday` と日本語 `火曜日` を確認した。今回の実機配信は `en`。

計画の「本体が PC の WebSocket に接続する」は未完了である。`WIFI_SSID_H` を空にして Wi-Fi を切ってある。パスワードをビルドに埋め込んでいない。ホスト側 WebSocket `ws://127.0.0.1:8000/ws/stackchan` は PC 内クライアントでのみ確認した。実機からの WS 接続は未実施。

今の本体は公式 1.5.1 ではない。戻すときは次である。SHA256 はフェーズ0どおり `411578a2ebca2cfe3541fdc32aeddbc4703cf912a5daa7e1253f69306d6e1d87`。

```
.venv/bin/esptool --port /dev/ttyACM0 write-flash 0x0 firmware/official/StackChan-UserDemo-V1.5.1.bin
```

```
いま動いている（フェーズ1の時計）

+---------------------------+        USB         +---------------------------+
| PC                        | -----------------> | StackChan                 |
|                           |  1秒ごと JSON      |                           |
|  中でやること             |  日付・時刻・曜日  |  中でやること             |
|    いまの日時を3行にする  |                    |    JSON を受け取る        |
|    曜日は英語か日本語     |                    |    液晶に3行描く          |
|                           | <----------------- |      2026/09/08           |
|                           |  描けた / 切れた   |      22:58:33             |
|                           |                    |      Tuesday              |
|                           |                    |    2.5秒来なければ        |
|                           |                    |      「未接続」           |
+---------------------------+                    +---------------------------+

Wi-Fi はまだ（未実施）

+---------------------------+     Wi-Fi 点線     +---------------------------+
| PC                        | - - - - - - - - -> | StackChan                 |
|  同じ JSON を待ち受け     |  パスワード未設定  |  Wi-Fi を起動していない   |
+---------------------------+                    +---------------------------+

74th は使っていない（会話の候補。時計は描けない）

+---------------------------+       Wi-Fi        +---------------------------+
| PC                        | <----------------> | StackChan                 |
|                           |  音声              |                           |
|  中でやること             |  状態              |  中でやること             |
|    聞く・話す・LLM        |  サーボ            |    マイクとスピーカー     |
|                           |  ※日時テキストなし|    画面は状態名と顔だけ   |
+---------------------------+                    +---------------------------+
```

---

## 詳細

### 1. 74th に時計メッセージがあるか

コマンド： git -C vendor/websocket-control-stackchan remote -v

- 目的： フェーズ0で選んだ土台のクローン先と URL を確認する

引数：
- `-C vendor/websocket-control-stackchan` — リポジトリルートへ cd せず、その Git を対象にする
- `remote` — リモート名を出す
- `-v` — fetch/push の URL も出す

結果：
```
origin	https://github.com/74th/websocket-control-stackchan.git (fetch)
origin	https://github.com/74th/websocket-control-stackchan.git (push)
```

コマンド： git -C vendor/websocket-control-stackchan log -1 --format='%H %s'

- 目的： 調べたコミットを固定する

引数：
- `-C vendor/websocket-control-stackchan` — 上と同じクローン
- `log` — コミット履歴
- `-1` — 最新 1 件
- `--format='%H %s'` — フルハッシュと件名だけ

結果：
```
ae5c4a7126ae199a20393c249f5feb07e99a42ab Merge pull request #65 from 74th/codex/update-license
```

コマンド： rg -n "clock|Clock|日付|曜日" vendor/websocket-control-stackchan/protobuf/websocket-message.proto

- 目的： protobuf に時計や日付のフィールドがあるか見る

引数：
- `-n` — 行番号を付ける
- `"clock|Clock|日付|曜日"` — 時計に関係しそうな語
- `vendor/websocket-control-stackchan/protobuf/websocket-message.proto` — 本体とホストが共有するメッセージ定義

結果：
```
（一致なし。終了コード 1）
```

コマンド： rg -n "MESSAGE_KIND_" vendor/websocket-control-stackchan/protobuf/websocket-message.proto

- 目的： 定義されているメッセージ種別の一覧を取る

引数：
- `-n` — 行番号を付ける
- `"MESSAGE_KIND_"` — enum の各値
- `vendor/websocket-control-stackchan/protobuf/websocket-message.proto` — 上と同じ proto

結果：
```
38:  MESSAGE_KIND_UNSPECIFIED = 0;
39:  MESSAGE_KIND_AUDIO_PCM = 1;
40:  MESSAGE_KIND_AUDIO_WAV = 2;
41:  MESSAGE_KIND_STATE_CMD = 3;
42:  MESSAGE_KIND_WAKE_WORD_EVT = 4;
43:  MESSAGE_KIND_STATE_EVT = 5;
44:  MESSAGE_KIND_SPEAK_DONE_EVT = 6;
45:  MESSAGE_KIND_SERVO_CMD = 7;
46:  MESSAGE_KIND_SERVO_DONE_EVT = 8;
47:  MESSAGE_KIND_FIRMWARE_METADATA = 9;
48:  MESSAGE_KIND_SERVER_METADATA = 10;
```

コマンド： rg -n "printf|stateToString" vendor/websocket-control-stackchan/firmware/src/display.cpp

- 目的： 画面に出している文字列が状態名だけか確認する

引数：
- `-n` — 行番号を付ける
- `"printf|stateToString"` — 状態バーへ書く呼び出し
- `vendor/websocket-control-stackchan/firmware/src/display.cpp` — 液晶描画

結果：
```
140:  GFXModule.printf("%s", stateToString(state));
```

`FirmwareMetadata` に `display_width` / `display_height` はあるが、ホストから3行テキストを送る body は無い。ここまでで 74th はフェーズ1の時計には使わないと決めた。

### 2. ホストの時計文字列

コマンド： ls -l firmware/clock_ws/src firmware/clock_ws/include firmware/clock_ws/platformio.ini host/

- 目的： 追加したファームとホストのファイルが揃っているか見る

引数：
- `-l` — サイズと更新時刻を出す
- `firmware/clock_ws/src` — 本体 `main.cpp`
- `firmware/clock_ws/include` — `config.h`（gitignore）とテンプレート
- `firmware/clock_ws/platformio.ini` — PlatformIO 環境
- `host/` — Python ホスト

結果：
```
-rw-rw-r-- 1 takuya takuya  278 Sep  8 23:25 firmware/clock_ws/platformio.ini

firmware/clock_ws/include:
total 8
-rw-rw-r-- 1 takuya takuya 281 Sep  8 23:26 config.h
-rw-rw-r-- 1 takuya takuya 281 Sep  8 23:25 config.template.h

firmware/clock_ws/src:
total 4
-rw-rw-r-- 1 takuya takuya 3449 Sep  8 23:32 main.cpp

host/:
total 16
-rw-rw-r-- 1 takuya takuya  788 Sep  8 23:25 clock_format.py
-rw-rw-r-- 1 takuya takuya 3351 Sep  8 23:26 clock_server.py
drwxrwxr-x 2 takuya takuya 4096 Sep  8 23:26 __pycache__
-rw-rw-r-- 1 takuya takuya  587 Sep  8 23:25 test_clock_format.py
```

コマンド： export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1

- 目的： システムに入っている pytest プラグイン（ROS の launch_testing など）を読ませず、このテストだけ走らせる

引数：
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` — pytest の自動プラグイン読込を止める

結果：
```
（環境変数をこのシェルに設定。stdout なし）
```

コマンド： .venv/bin/pytest -q host/test_clock_format.py

- 目的： 指定例 `2026/09/08` / `22:58:33` / `Tuesday` と日本語曜日がホストで出るか確認する

引数：
- `-q` — 短い結果
- `host/test_clock_format.py` — 時計フォーマットの単体テスト

結果：
```
...                                                                      [100%]
3 passed in 0.00s
```

コマンド： .venv/bin/python - <<'PY' （datetime(2026, 9, 8, 22, 58, 33) で format_clock_lines en/ja と clock_message を印字）

- 目的： テストと同じ入力を目で見る

引数：
- `-` — 標準入力のスクリプトを実行
- `<<'PY'` — ヒアドキュメント。変数展開しない
- `sys.path.insert(0, "host")` — `host/` を import 対象にする
- `datetime(2026, 9, 8, 22, 58, 33)` — 計画書の表示例と同じ日時
- `"en"` / `"ja"` — 曜日言語

結果：
```
['2026/09/08', '22:58:33', 'Tuesday']
['2026/09/08', '22:58:33', '火曜日']
{'type': 'clock', 'lines': ['2026/09/08', '22:58:33', 'Tuesday']}
```

### 3. ファーム設定（Wi-Fi は空）

コマンド： diff -u firmware/clock_ws/include/config.template.h firmware/clock_ws/include/config.h

- 目的： 秘密情報をテンプレートへ書いていないか、実ビルド用 `config.h` との差を見る

引数：
- `-u` — unified diff
- `firmware/clock_ws/include/config.template.h` — git 管理する雛形。SSID は空
- `firmware/clock_ws/include/config.h` — ビルドが読むファイル。gitignore

結果：
```
config.h matches template
```

（`diff` の終了コードは 0。差が無いので差分本文は出ず、確認用に `&& echo 'config.h matches template'` を付けた）

テンプレートの中身は `WIFI_SSID_H ""`、`SERVER_HOST_H "192.168.10.14"`、`SERVER_PORT_H 8000`、`SERVER_PATH_H "/ws/stackchan"`。SSID が空だとファームは Wi-Fi も WebSocket クライアントも起動せず、USB シリアルだけ読む。

コマンド： nmcli -t -f active,ssid dev wifi

- 目的： この PC が乗っている 2.4GHz SSID を記録する（パスワードは取らない）

引数：
- `-t` — 区切り文字だけの短い出力
- `-f active,ssid` — 接続中かと SSID だけ
- `dev wifi` — Wi-Fi デバイスの一覧

結果：
```
yes:aterm-60cc5a-a
```

コマンド： ip -br addr

- 目的： ホストの LAN IP がテンプレートの `192.168.10.14` と一致するか見る

引数：
- `-br` — 1 行要約
- `addr` — アドレス一覧

結果：
```
lo               UNKNOWN        127.0.0.1/8 ::1/128 
enp3s0           DOWN           
wlp0s20f3        UP             192.168.10.14/24 fd90:3c4a:d783:11d4:a0ae:11f3:ca3a:470/64 fd90:3c4a:d783:11d4:c659:fbe1:7c33:63e2/64 fd90:3c4a:d783:11d4:b5f9:5347:8079:59a7/64 fe80::e9db:9a3d:2bf4:8c2d/64 
tailscale0       UNKNOWN        100.114.199.5/32 fd7a:115c:a1e0::373a:c707/128 fe80::d5e5:aa50:e3da:cf7c/64 
```

### 4. ビルドと書き込み

コマンド： .venv/bin/pio --version

- 目的： 使う PlatformIO の版を固定する

引数：
- `--version` — Core の版を出す

結果：
```
PlatformIO Core, version 6.2.0
```

コマンド： .venv/bin/python -c 'import serial,websockets,pytest; print("pyserial", serial.__version__); print("websockets", websockets.__version__); print("pytest", pytest.__version__)'

- 目的： ホストとテストに使う Python ライブラリの版を固定する

引数：
- `-c` — 1 行スクリプト
- `serial` — USB シリアル
- `websockets` — ホストの WS サーバ
- `pytest` — 単体テスト

結果：
```
pyserial 3.5
websockets 17.1
pytest 9.1.1
```

コマンド： .venv/bin/pio run -e m5stack-cores3

- 目的： CoreS3 向け時計ファームをリンクできるか確認する

引数：
- `run` — ビルド
- `-e m5stack-cores3` — `platformio.ini` の公式 CoreS3 環境
- 作業ディレクトリ `firmware/clock_ws`
- 全文: `agent_reports/phase1_artifacts/pio_build.txt`

結果：
```
Processing m5stack-cores3 (platform: espressif32; board: m5stack-cores3; framework: arduino)
--------------------------------------------------------------------------------
Verbose mode can be enabled via `-v, --verbose` option
CONFIGURATION: https://docs.platformio.org/page/boards/espressif32/m5stack-cores3.html
PLATFORM: Espressif 32 (7.1.2) > M5Stack CoreS3
HARDWARE: ESP32S3 240MHz, 320KB RAM, 16MB Flash
DEBUG: Current (cmsis-dap) External (cmsis-dap, esp-bridge, esp-builtin, esp-prog, iot-bus-jtag, jlink, minimodule, olimex-arm-usb-ocd, olimex-arm-usb-ocd-h, olimex-arm-usb-tiny-h, olimex-jtag-tiny, tumpa)
PACKAGES: 
 - framework-arduinoespressif32 @ 4.20017.260907+sha.dcc1105b 
 - tool-esptoolpy @ 2.41100.260830 (4.11.0) 
 - toolchain-riscv32-esp @ 8.4.0+2021r2-patch5 
 - toolchain-xtensa-esp32s3 @ 8.4.0+2021r2-patch5
LDF: Library Dependency Finder -> https://bit.ly/configure-pio-ldf
LDF Modes: Finder ~ chain, Compatibility ~ soft
Found 37 compatible libraries
Scanning dependencies...
Dependency Graph
|-- M5Unified @ 0.2.21
|-- WebSockets @ 2.7.3
|-- ArduinoJson @ 7.4.3
|-- WiFi @ 2.0.0
Building in release mode
Compiling .pio/build/m5stack-cores3/src/main.cpp.o
Linking .pio/build/m5stack-cores3/firmware.elf
Retrieving maximum program size .pio/build/m5stack-cores3/firmware.elf
Checking size .pio/build/m5stack-cores3/firmware.elf
Advanced Memory Usage is available via "PlatformIO Home > Project Inspect"
RAM:   [=         ]   8.4% (used 27628 bytes from 327680 bytes)
Flash: [==        ]  15.6% (used 1022945 bytes from 6553600 bytes)
Building .pio/build/m5stack-cores3/firmware.bin
esptool.py v4.11.0
Creating esp32s3 image...
Merged 2 ELF sections
Successfully created esp32s3 image.
========================= [SUCCESS] Took 6.46 seconds =========================
```

コマンド： .venv/bin/pio run -e m5stack-cores3 -t upload --upload-port /dev/ttyACM0

- 目的： 実機フラッシュへ時計ファームを書く

引数：
- `run` — ビルド後にターゲットを実行
- `-e m5stack-cores3` — 上と同じ環境
- `-t upload` — 書き込み
- `--upload-port /dev/ttyACM0` — USB-Serial/JTAG のポートを固定する
- 作業ディレクトリ `firmware/clock_ws`
- 全文: `agent_reports/phase1_artifacts/pio_upload.txt`

結果：
```
Chip is ESP32-S3 (QFN56) (revision v0.2)
Features: WiFi, BLE
Crystal is 40MHz
USB mode: USB-Serial/JTAG
MAC: 68:ee:8f:d7:49:f8
...
Wrote 1023312 bytes (685239 compressed) at 0x00010000 in 5.8 seconds (effective 1416.9 kbit/s)...
Hash of data verified.

Leaving...
Hard resetting via RTS pin...
========================= [SUCCESS] Took 12.03 seconds =========================
```

### 5. USB シリアルで時計と切断

ポートを開くと ESP32-S3 は `rst:0x15 USB_UART_CHIP_RESET` で再起動する。開いたまま待つ。メッセージごとに開き直さない。

コマンド： .venv/bin/python - <<'PY' （`/dev/ttyACM0` を開き CLOCK_FW_READY を待ち、時計 JSON を 1 行送り、CLOCK_APPLIED と CLOCK_TIMEOUT を待つ）

- 目的： 起動、時計描画、2.5 秒無通信の切断表示をシリアル ACK で確認する

引数：
- `-` — 標準入力のスクリプト
- `serial.Serial("/dev/ttyACM0", 115200, timeout=0.2)` — USB シリアル
- `ser.dtr = False` / `ser.rts = False` — 開き直したあとにダウンロードモードへ戻さない
- `clock_message(datetime(2026, 9, 8, 22, 58, 33), "en")` — 計画書と同じ3行
- 保存先 `agent_reports/phase1_artifacts/serial_verify.txt`

結果：
```
SENT {"type": "clock", "lines": ["2026/09/08", "22:58:33", "Tuesday"]}
---RECV---
ESP-ROM:esp32s3-20210327
Build:Mar 27 2021
rst:0x15 (USB_UART_CHIP_RESET),boot:0x28 (SPI_FAST_FLASH_BOOT)
Saved PC:0x42073aee
SPIWP:0xee
mode:DIO, clock div:1
load:0x3fce3808,len:0x4bc
load:0x403c9700,len:0xbd8
load:0x403cc700,len:0x2a0c
entry 0x403c98d0
[  1087][I][esp32-hal-psram.c:96] psramInit(): PSRAM enabled
[  1111][I][M5GFX.cpp:1060] init_impl(): [M5GFX] [Autodetect] load from NVS : board:27
[  1120][I][esp32-hal-i2c.c:75] i2cInit(): Initialising I2C Master: sda=12 scl=11 freq=100000
[  1133][I][M5GFX.cpp:1780] autodetect(): [M5GFX] [Autodetect] board_M5StackChan
[  1293][I][esp32-hal-i2c.c:75] i2cInit(): Initialising I2C Master: sda=12 scl=11 freq=100000
[  1304][I][M5GFX.cpp:597] initPanelByTouchVersion(): [M5GFX] CoreS3 touch CIPHER:0x64 / FIRMID:0x10 / VENDID:0x11, panel:ILI9342C
[  1316][I][esp32-hal-i2c.c:75] i2cInit(): Initialising I2C Master: sda=12 scl=11 freq=100000
[  1361][I][esp32-hal-i2c.c:75] i2cInit(): Initialising I2C Master: sda=12 scl=11 freq=100000
[  1371][I][esp32-hal-i2c.c:75] i2cInit(): Initialising I2C Master: sda=12 scl=11 freq=100000
CLOCK_FW_READY
CLOCK_APPLIED
CLOCK_TIMEOUT
---MARKERS---
CLOCK_FW_READY True
CLOCK_APPLIED True
CLOCK_TIMEOUT True
```

画面そのものの写真は取っていない。ファームは `CLOCK_APPLIED` の直前に3行を描き、`CLOCK_TIMEOUT` の直前に日本語フォントで「未接続」を描く。パネルは起動ログどおり ILI9342C の公式 StackChan。

### 6. ホスト WebSocket（PC 内のみ）

コマンド： .venv/bin/python host/clock_server.py --ws-host 127.0.0.1 --ws-port 8000

- 目的： 実機なしで、ホストが `ws://127.0.0.1:8000/ws/stackchan` に時計 JSON を流せるか見る

引数：
- `host/clock_server.py` — 1Hz 配信サーバ
- `--ws-host 127.0.0.1` — ループバックだけ待つ
- `--ws-port 8000` — テンプレートと同じポート
- クライアントは同じスクリプト内で `websockets.connect("ws://127.0.0.1:8000/ws/stackchan")`
- 保存先 `agent_reports/phase1_artifacts/ws_local.txt`

結果：
```
SERVER:
websocket ws://127.0.0.1:8000/ws/stackchan
ws client ('127.0.0.1', 37792) path=/ws/stackchan
ws client disconnected

CLIENT:
{"type": "clock", "lines": ["2026/09/08", "23:33:55", "Tuesday"]}
```

これは PC 内の接続である。本体が Wi-Fi で同じパスに来る確認ではない。

### 7. 実機 WebSocket

コマンド： （未実行）本体を AP `aterm-60cc5a-a` に乗せて `ws://192.168.10.14:8000/ws/stackchan` へ接続する

- 目的： 計画どおり無線で時計を出す

引数： なし

結果：
```
（未実行）WIFI_SSID_H が空。パスワードを config.h に書いていない。
```

### 8. 1Hz のシリアル配信

コマンド： .venv/bin/python host/clock_server.py --serial /dev/ttyACM0 --weekday en --tz Asia/Tokyo

- 目的： 実機へ毎秒いまの日時を送り、時計画面を維持する

引数：
- `--serial /dev/ttyACM0` — USB シリアルへ JSON 行を書く
- `--weekday en` — 英語曜日（計画の初期表示）
- `--tz Asia/Tokyo` — ホストのタイムゾーン
- 保存先（起動直後） `agent_reports/phase1_artifacts/clock_server_serial.txt`

結果：
```
serial opened /dev/ttyACM0
websocket ws://0.0.0.0:8000/ws/stackchan
```

このプロセスは確認後も動かしたままにしてある。止めると 2.5 秒で画面は「未接続」に戻る。日本語曜日にするときは `--weekday ja` で再起動する。
