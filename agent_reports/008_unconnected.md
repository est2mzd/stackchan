# 画面が「未接続」になる件

## 背景

フェーズ1のファームは、PC から時計 JSON が約 2.5 秒来ないと液晶に「未接続」を出す。ユーザが pytest のあと本体を見ると、その文字になっていた。

## 目的

| 完了条件 | 状態 |
| --- | --- |
| 「未接続」の原因を特定する | 完了。ホストが動いていなかった |
| USB で時計 JSON を送り、本体が `CLOCK_APPLIED` を返す | 完了 |
| ホストを止めない運用を README に書く | 完了 |

## 結論

故障ではない。PC 側のホストが止まっていると、本体は設計どおり「未接続」になる。確認時点で `clock_server.py` も `server.py` も動いていなかった。本体 USB（`303a:1001`、`/dev/ttyACM0`）は見えていた。

ホストを起動したあと、シリアルに `CLOCK_FW_READY` と連続する `CLOCK_APPLIED` が出た。`CLOCK_TIMEOUT` は出ていない。ホストを動かしたままなら画面は日付・時刻・曜日になる。止めると約 2.5 秒でまた「未接続」になる。pytest だけでは画面は動かない。

いま動かしているコマンド:

```
.venv/bin/python host/clock_server.py --serial /dev/ttyACM0 --weekday en --tz Asia/Tokyo
```

生ログ: `agent_reports/phase1_artifacts/clock_reconnect_20260909.txt`

```
+---------------------------+        USB         +---------------------------+
| PC                        | -----------------> | StackChan                 |
|                           |  1秒ごと JSON      |                           |
|  中でやること             |  日付・時刻・曜日  |  中でやること             |
|    いまの日時を3行にする  |                    |    JSON を受け取る        |
|    ホストを止めない       |                    |    液晶に3行描く          |
|                           | <----------------- |      YYYY/MM/DD           |
|                           |  描けた            |      HH:MM:SS             |
|                           |  CLOCK_APPLIED     |      Tuesday              |
+---------------------------+                    +---------------------------+

ホストを止めたあと（再現した状態）

+---------------------------+     USB 点線       +---------------------------+
| PC                        | - - - - - - - - -> | StackChan                 |
|                           |  JSON を送らない   |                           |
|  中でやること             |  （未実施）        |  中でやること             |
|    pytest だけ動かす      |                    |    2.5秒来なければ        |
|                           |                    |      「未接続」           |
+---------------------------+                    +---------------------------+
```

## 詳細

コマンド： lsusb | grep -E '303a:1001|M5Stack|Espressif'

- 目的： PC が本体を USB デバイスとして認識しているか確認する

引数：
- パイプ `grep -E` — Espressif USB JTAG の ID だけ残す
- `'303a:1001|M5Stack|Espressif'` — 本体の USB ID と名前

結果：
```
Bus 003 Device 010: ID 303a:1001 Espressif USB JTAG/serial debug unit
```

コマンド： ls -l /dev/ttyACM* /dev/ttyUSB* 2>/dev/null

- 目的： シリアルの実名と権限を見る

引数：
- `-l` — 権限・所有者を出す
- `/dev/ttyACM*` — ESP32-S3 内蔵 USB シリアルの名前
- `/dev/ttyUSB*` — USB-UART 変換チップの名前。無い機体もある
- `2>/dev/null` — グロブ 0 件のエラーメッセージを捨てる

結果：
```
crw-rw-rw- 1 root plugdev 166, 0 Sep  9 20:50 /dev/ttyACM0
```

`/dev/ttyUSB*` は無く、シェルがそのグロブを失敗扱いにした。`ttyACM0` 自体は存在する。

コマンド： pgrep -af 'clock_server.py|host/server.py'

- 目的： 時計 JSON を送るホストが動いているか確認する

引数：
- `-a` — コマンド行全体を出す
- `-f` — コマンド行でマッチする
- `'clock_server.py|host/server.py'` — 時計ホストと統合ホスト

結果：
```
（プロセスなし。スクリプト側で no host running と表示）
```

コマンド： fuser -v /dev/ttyACM0

- 目的： シリアルを他プロセスが掴んでいないか確認する

引数：
- `-v` — 使っているプロセスを出す
- `/dev/ttyACM0` — 本体のシリアル

結果：
```
（使用者なし）
```

コマンド： .venv/bin/python host/clock_server.py --serial /dev/ttyACM0 --weekday en --tz Asia/Tokyo

- 目的： 1 秒ごとに時計 JSON を送り、画面の「未接続」を解消する

引数：
- `host/clock_server.py` — 時計専用ホスト
- `--serial /dev/ttyACM0` — USB で送る
- `--weekday en` — 曜日を英語にする
- `--tz Asia/Tokyo` — 日本時間

結果：
```
serial opened /dev/ttyACM0
websocket ws://0.0.0.0:8000/ws/stackchan
CLOCK_FW_READY
CLOCK_APPLIED
CLOCK_APPLIED
```

続きは `agent_reports/phase1_artifacts/clock_reconnect_20260909.txt`。ポートを開いた瞬間に `rst:0x15 (USB_UART_CHIP_RESET)` が出るのは従来どおり。起動後は `CLOCK_APPLIED` が連続し、`CLOCK_TIMEOUT` は出ていない。このプロセスは止めていない。
