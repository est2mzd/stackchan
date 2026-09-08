# フェーズ0 実施報告

実施日: 2026-09-08  
入力: `user_directions/001_objective.md`、`agent_reports/001_plan.md`  
作業ディレクトリ: `/home/takuya/work/stackchan`  
生ログ: `agent_reports/phase0_artifacts/`  
ポート名 `/dev/ttyACM0` は環境で変わる。

---

## 背景

StackChan（M5Stack 公式完成品、2026-08 購入）を、スマホアプリではなく PC または Jetson 上のプログラムから使いたい。やりたいことは次の3つである。

1. 本体マイクで話し、PC/Jetson の Local LLM または ChatGPT が答え、スピーカーと画面文字で返す
2. 「時計モード」と言うと画面に日付・時刻・曜日を出す
3. Google Calendar の予定を X 分前に音と画面で知らせる

出荷時ファームはスマートフォンアプリ「StackChan World」前提である。アプリ連携は目的ではない。参考記事では、出荷ファームが古いとペアリングが `No devices found` で詰むと報告されている。

- 参考: [スタックちゃんがアプリとペアリングできない原因は出荷時ファームだった](https://zenn.dev/shogaku/articles/stackchan-pairing-firmware)
- 公式ドキュメント: [docs.m5stack.com/ja/StackChan](https://docs.m5stack.com/ja/StackChan)

計画（`001_plan.md`）では公式アプリ経路は追わない。本体を入出力、PC を頭脳にする。フェーズ0は、つながっている物、今のファーム、公式への戻し方、この Linux PC からフラッシュ工具が使えるかを確定する。

---

## 目的

1. 本体の SKU、USB ポート、起動ログ上のファーム版数を記録する
2. 公式最新ファームのバイナリを PC に保存し、いつでも戻せるようにする
3. この Linux PC から `esptool` で本体フラッシュにアクセスできることを確認する
4. 以降の実装の土台にするファームウェアを1つ選ぶ

計画には「候補ファームを1つ焼いて画面と Wi-Fi を見る」もある。土台がビルド時に Wi-Fi パスワードを要求するなら、未設定のまま公式ファームを消さない。

---

## 結論

実機は公式 StackChan（SKU `m5stack-stack-chan`、製品としては K151）。USB は `303a:1001` で `/dev/ttyACM0`。チップは ESP32-S3 revision v0.2、フラッシュ 16MB、PSRAM 8MB、MAC `68:ee:8f:d7:49:f8`。

今のファームは公式 **StackChan-UserDemo 1.5.1**（2026-07-31）。M5Burner カタログの最新と同じ。同じ bin を `firmware/official/StackChan-UserDemo-V1.5.1.bin` に保存した。SHA256 は `411578a2ebca2cfe3541fdc32aeddbc4703cf912a5daa7e1253f69306d6e1d87`。

`esptool` 5.4.0 で `flash-id` と `read-flash` に成功した。本体はすでに最新公式なので、確認目的の再書き込みはしていない。

シリアルは当初 `dialout` 未加入で開けなかった。udev を入れて一般ユーザで開けるようにした。

土台は [74th/websocket-control-stackchan](https://github.com/74th/websocket-control-stackchan) の `env:m5stack-official-stackchan`。Wi-Fi SSID/パスワードがビルド時必須のため、**候補の書き込みはフェーズ1へ送った**。次に必要なのは 2.4GHz の SSID とパスワードである。ホスト IP の初期値は `192.168.10.14`。

かかと側（ベース側）USB-C だけをデータ対応ケーブルで繋ぐ。両方の USB-C に同時給電しない。

```
フェーズ0で確認した実体（公式ファームのまま）

+---------------------------+        USB         +---------------------------+
| PC                        | <----------------> | StackChan                 |
|                           |  フラッシュ読書き  |                           |
|  中でやること             |  起動ログ          |  中でやること             |
|    esptool で中身を見る   |                    |    公式 1.5.1 が動く      |
|    シリアルでログを取る   |                    |    液晶・マイクはある     |
|                           |                    |    PC からは時計も会話も  |
|                           |                    |    制御していない         |
+---------------------------+                    +---------------------------+

使わない経路

+---------------------------+                    +---------------------------+
| スマホ                    | ------ x ------->  | StackChan                 |
|  StackChan World          |   本計画の外       |  公式クラウド前提         |
+---------------------------+                    +---------------------------+
```

---

## 詳細

### 1. USB で本体が見えるか

コマンド： lsusb

- 目的： PC が本体を USB デバイスとして認識しているか確認する

引数： なし

結果：
```
Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub
Bus 002 Device 001: ID 1d6b:0003 Linux Foundation 3.0 root hub
Bus 003 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub
Bus 003 Device 002: ID 046d:c548 Logitech, Inc. Logi Bolt Receiver
Bus 003 Device 003: ID 04f2:b729 Chicony Electronics Co., Ltd Chicony USB2.0 Camera
Bus 003 Device 004: ID 8087:0033 Intel Corp. AX211 Bluetooth
Bus 003 Device 009: ID 303a:1001 Espressif USB JTAG/serial debug unit
Bus 004 Device 001: ID 1d6b:0003 Linux Foundation 3.0 root hub
```

コマンド： ls -l /dev/serial/by-id/

- 目的： USB シリアルの安定名と /dev/ttyACM0 の対応を取る

引数：
- `-l` — 権限とリンク先 `->` を出す
- `/dev/serial/by-id/` — USB シリアルの安定名。抜き差しで ttyACM 番号がずれても同じデバイスを指す

結果：
```
total 0
lrwxrwxrwx 1 root root 13 Sep  8 22:01 usb-Espressif_USB_JTAG_serial_debug_unit_68:EE:8F:D7:49:F8-if00 -> ../../ttyACM0
```

コマンド： ls -l /dev/ttyACM* /dev/ttyUSB* 2>/dev/null

- 目的： シリアルの実名（ttyACM か ttyUSB か）と権限を見る

引数：
- `-l` — 権限・所有者・グループを出す
- `/dev/ttyACM*` — ESP32-S3 内蔵 USB-Serial/JTAG の名前
- `/dev/ttyUSB*` — USB-UART 変換チップの名前。無い機体もあるので両方見る
- `2>/dev/null` — 片方のグロブが 0 件のときの `No such file` を捨てる

結果：
```
crw-rw---- 1 root dialout 166,  0 Sep  8 22:01 /dev/ttyACM0
```

コマンド： ip -br addr

- 目的： フェーズ1のサーバになる PC の LAN IP を取る

引数：
- `-br` — brief。名前・状態・アドレスだけ出す
- `addr` — IP アドレスを表示する。フェーズ1のサーバ宛先になる

結果：
```
lo               UNKNOWN        127.0.0.1/8 ::1/128
enp3s0           DOWN
wlp0s20f3        UP             192.168.10.14/24 fd90:3c4a:d783:11d4:a0ae:11f3:ca3a:470/64 ...
tailscale0       UNKNOWN        100.114.199.5/32 ...
```

### 2. シリアルを自分のユーザで開けるか

コマンド： ls -l /dev/ttyACM0

- 目的： ポートの所有者・グループ・権限を見る

引数：
- `-l` — 権限・所有者・グループを出す。`660` なら dialout 以外は開けない
- `/dev/ttyACM0` — 上で確定したポート

結果：
```
crw-rw---- 1 root dialout 166, 0 Sep  8 22:01 /dev/ttyACM0
```

コマンド： id

- 目的： 今のユーザが dialout グループに入っているか見る

引数： なし

結果：
```
uid=1000(takuya) gid=1000(takuya) groups=1000(takuya),4(adm),24(cdrom),27(sudo),30(dip),46(plugdev),100(users),114(lpadmin)
```

コマンド： python3 -c 'import os; print("R", os.access("/dev/ttyACM0", os.R_OK), "W", os.access("/dev/ttyACM0", os.W_OK))'

- 目的： 今のユーザでポートを読み書きできるか確認する

引数：
- `-c` — ファイルを作らず、後ろの文字列を Python として実行する
- `os.R_OK` / `os.W_OK` — 今のユーザが読めるか・書けるか

結果：
```
R False
W False
```

コマンド： python3 - <<'PY' ... Serial("/dev/ttyACM0", 115200, timeout=1) ...

- 目的： esptool と同じ開き方で Permission denied を再現する

引数：
- `-` — 標準入力からスクリプトを読む
- `<<'PY'` — ヒアドキュメント。変数展開しない
- `115200` — ESP の既定ボーレート
- `timeout=1` — 1 秒で読み打ち切り

結果：
```
open failed: SerialException [Errno 13] could not open port /dev/ttyACM0: [Errno 13] Permission denied: '/dev/ttyACM0'
```

コマンド： pkexec chmod a+rw /dev/ttyACM0

- 目的： 一時的にポートを誰でも開けるようにする

引数：
- `pkexec` — デスクトップのパスワードダイアログで root 権限を取る
- `chmod` — 権限を変える
- `a+rw` — 全員に read/write を足す（一時的。USB 抜きで戻る）
- `/dev/ttyACM0` — 対象ポート

結果：
```
（標準出力なし。終了コード 0）
```

コマンド： ls -l /dev/ttyACM0

- 目的： chmod 後に権限が rw-rw-rw- になったか確認する

引数：
- `-l` — 権限が `rw-rw-rw-` になったかを確認する
- `/dev/ttyACM0` — 対象ポート

結果：
```
crw-rw-rw- 1 root dialout 166, 0 Sep  8 22:01 /dev/ttyACM0
```

コマンド： cat tools/99-esp32s3-usbjtag.rules

- 目的： 永続用 udev 規則の中身を確認する

引数：
- `tools/99-esp32s3-usbjtag.rules` — 永続用 udev 規則の中身確認。VID/PID `303a:1001` を `0666` / `plugdev` にする

結果：
```
SUBSYSTEM=="tty", ATTRS{idVendor}=="303a", ATTRS{idProduct}=="1001", MODE="0666", GROUP="plugdev"
SUBSYSTEM=="usb", ATTRS{idVendor}=="303a", ATTRS{idProduct}=="1001", MODE="0666", GROUP="plugdev"
```

コマンド： pkexec bash -c "cp .../99-esp32s3-usbjtag.rules /etc/udev/rules.d/ && chmod 644 ... && udevadm control --reload-rules && udevadm trigger --subsystem-match=tty --subsystem-match=usb"

- 目的： 抜き差し後もポートを開けるよう udev を入れる

引数：
- `pkexec bash -c` — 複数コマンドを root で一連実行する
- `cp ... /etc/udev/rules.d/` — 規則をシステムへ置く。ここに置かないとカーネルが読まない
- `chmod 644` — 規則ファイルは実行ビット不要
- `udevadm control --reload-rules` — 規則を読み直す
- `udevadm trigger --subsystem-match=tty --subsystem-match=usb` — 抜差しなしで既存 tty/usb に規則を当てる

結果：
```
（標準出力なし。終了コード 0）
```

コマンド： ls -l /etc/udev/rules.d/99-esp32s3-usbjtag.rules /dev/ttyACM0 /dev/bus/usb/003/009

- 目的： udev が規則ファイルとデバイスに当たったか確認する

引数：
- `-l` — 権限確認
- 3 パス — 規則ファイル、シリアル、`lsusb` の Bus 003 Device 009 に対応する USB ノード

結果：
```
-rw-r--r-- 1 root root 396 Sep  8 22:42 /etc/udev/rules.d/99-esp32s3-usbjtag.rules
crw-rw-rw- 1 root dialout 166,   0 Sep  8 22:40 /dev/ttyACM0
crw-rw-rw- 1 root plugdev 189, 264 Sep  8 22:42 /dev/bus/usb/003/009
```

### 3. esptool を入れる

コマンド： cd /home/takuya/work/stackchan

- 目的： 以降の相対パスの起点をリポジトリルートにする

引数：
- `/home/takuya/work/stackchan` — このリポジトリのルート。以降の相対パスの起点

結果：
```
（標準出力なし。カレントディレクトリが変わる）
```

コマンド： python3 -m venv .venv

- 目的： システム Python を汚さず esptool を入れる箱を作る

引数：
- `-m venv` — 標準の仮想環境モジュール
- `.venv` — 環境を置くディレクトリ。システム Python を汚さない

結果：
```
（標準出力なし。`.venv/bin/python` ができる）
```

コマンド： uv pip install --python /home/takuya/work/stackchan/.venv/bin/python esptool pyserial

- 目的： フラッシュ工具とシリアル読み取り用ライブラリを入れる

引数：
- `--python .../.venv/bin/python` — 入れる先のインタプリタ。指定しないと別環境に入ることがある
- `esptool` — ESP32 フラッシュ工具
- `pyserial` — 起動ログ取得用

結果：
```
Resolved 19 packages in 352ms
Installed 19 packages in 6ms
 + esptool==5.4.0
 + pyserial==3.5
 ...
```

コマンド： .venv/bin/esptool version

- 目的： 入れた esptool の版を確認する

引数：
- `.venv/bin/esptool` — venv 内の実行ファイル。PATH 上の apt 版と取り違えない
- `version` — チップに触らず版だけ出す

結果：
```
esptool v5.4.0
5.4.0
```

### 4. チップとフラッシュ容量を読む（消さない）

コマンド： .venv/bin/esptool --port /dev/ttyACM0 flash-id

- 目的： チップ種別とフラッシュ容量を読む（中身は消さない）

引数：
- `--port /dev/ttyACM0` — 対象シリアル。省略すると別ポートを掴むことがある
- `flash-id` — チップとフラッシュ容量を読む。中身は消さない。画面は一瞬再起動する

結果：
```
esptool v5.4.0
Serial port /dev/ttyACM0:
Connecting...
Detecting chip type... ESP32-S3
Connected to ESP32-S3 on /dev/ttyACM0:
Chip type:          ESP32-S3 (QFN56) (revision v0.2)
Features:           Wi-Fi, BT 5 (LE), Dual Core + LP Core, 240MHz
Crystal frequency:  40MHz
USB mode:           USB-Serial/JTAG
MAC:                68:ee:8f:d7:49:f8

Uploading stub flasher...
Running stub flasher...
Stub flasher running.

Flash Memory Information:
=========================
Manufacturer: 46
Device: 4018
Detected flash size: 16MB
Flash type set in eFuse: quad (4 data lines)
Flash voltage set by a strapping pin: 3.3V

Hard resetting via RTS pin...
```

コマンド： .venv/bin/esptool --port /dev/ttyACM0 --chip esp32s3 read-flash 0x0 0x1000 agent_reports/phase0_artifacts/flash-head.bin

- 目的： 先頭が ESP イメージか確認するため 4KiB 読む

引数：
- `--port /dev/ttyACM0` — 対象シリアル
- `--chip esp32s3` — チップ種別を固定する
- `read-flash` — フラッシュをファイルへ読む。消さない
- `0x0` — 開始オフセット（先頭）
- `0x1000` — 読む長さ 4096 バイト。ESP マジック `e9` の確認用
- `flash-head.bin` — 保存先

結果：
```
Read 4096 bytes from 0x00000000 in 0.0 seconds (1159.7 kbit/s) to 'agent_reports/phase0_artifacts/flash-head.bin'.
Hard resetting via RTS pin...
```

コマンド： od -An -tx1 -N 16 agent_reports/phase0_artifacts/flash-head.bin

- 目的： マジックバイト e9 を目で確認する

引数：
- `-An` — アドレス列を出さない
- `-tx1` — 十六進、1 バイト単位
- `-N 16` — 先頭 16 バイトだけ
- `flash-head.bin` — 直前に読んだファイル

結果：
```
 e9 03 02 4f c4 89 3c 40 ee 00 00 00 09 00 00 00
```

### 5. 起動ログから今のアプリ版数を取る

コマンド： .venv/bin/python - <<'PY' （シリアルを 12 秒読んで boot.log に保存）

- 目的： 起動ログを保存し、版数を後で抜けるようにする

引数：
- `-` — 標準入力からスクリプトを読む
- `115200` — ESP-IDF の既定ボーレート
- `timeout=0.2` — 1 回の read 待ち秒
- `dtr=False` / `rts=False` — 制御線を下げたまま。上げるとダウンロードモードに入ることがある
- `+ 12` — 12 秒で打ち切る。ポートを開くと本体は再起動する（`USB_UART_CHIP_RESET`）

結果：
```
（標準出力は起動ログ全文。8438 bytes を agent_reports/phase0_artifacts/boot.log に保存）
```

コマンド： grep -E "App version|Project name|Compile time|ESP-IDF:|SKU=|esp_psram: Found|USB_UART_CHIP_RESET" agent_reports/phase0_artifacts/boot.log

- 目的： 公式か、何の版か、SKU を抜く

引数：
- `-E` — 拡張正規表現。`A|B` が使える
- `"App version|..."` — 版特定に使うキーだけ残す
- `boot.log` — 保存済みログ。開き直すとまた再起動するのでファイルを grep する

結果：
```
rst:0x15 (USB_UART_CHIP_RESET),boot:0x28 (SPI_FAST_FLASH_BOOT)
I (676) esp_psram: Found 8MB PSRAM device
I (692) app_init: Project name:     stack-chan
I (696) app_init: App version:      1.5.1
I (700) app_init: Compile time:     Jul 31 2026 10:38:34
I (709) app_init: ESP-IDF:          v5.5.4
I (826) Board: UUID=5f573ecd-938f-4661-837e-bf45f3a6a045 SKU=m5stack-stack-chan
```

コマンド： grep -E "ILI9342|Camera init|Si12T|PCF8563|BMI270|ScsServo|timezone|AI.AGENT|SETUP" agent_reports/phase0_artifacts/boot.log

- 目的： 液晶・カメラ・サーボなどが初期化できたか抜く

引数：
- `-E` — 拡張正規表現
- パターン — 液晶・カメラ・タッチ・RTC・IMU・サーボ・公式アプリ名
- `boot.log` — 同じ起動ログ

結果：
```
I (1086) M5Stack-StackChan-Board: CIPHER:0x64 / FIRMID:0x10 / VENDID:0x11, panel:ILI9342C
I (1286) StackChanCamera: Camera init success
I (1356) Si12T: Si12T initialized, version: 0.0.2
[info] [HAL-RTC] PCF8563 init ok
[info] [HAL-RTC] load timezone from nvs: JST-9
[info] [HAL-IMU] BMI270 init ok
[info] [ScsServo] id: 1 get zero pos: 471 from settings
[info] [ScsServo] id: 2 get zero pos: 635 from settings
[info] [AI.AGENT] on create
[info] [SETUP] on create
```

コマンド： grep -E "Partition Table|ota_0|ota_1|Loaded app from partition" agent_reports/phase0_artifacts/boot.log

- 目的： 戻すときに 0x0 から書く根拠（今の OTA スロット）を取る

引数：
- `-E` — 拡張正規表現
- パターン — OTA スロットと、今どのオフセットから起動したか
- `boot.log` — 同じ起動ログ

結果：
```
I (51) boot: Partition Table:
I (80) boot:  3 ota_0            OTA app          00 10 00020000 004f0000
I (86) boot:  4 ota_1            OTA app          00 11 00510000 004f0000
I (666) boot: Loaded app from partition at offset 0x510000
```

### 6. 公式 bin を保存する

コマンド： mkdir -p firmware/official

- 目的： 公式 bin の保存先ディレクトリを作る

引数：
- `-p` — 途中のディレクトリも作る。既にあってもエラーにしない
- `firmware/official` — 公式 bin の置き場

結果：
```
（標準出力なし）
```

コマンド： curl -fsSL "https://m5burner-api.m5stack.com/api/firmware" -o /tmp/m5burner-firmware.json

- 目的： 公式ファームの版一覧 JSON を取る

引数：
- `-f` — HTTP エラーを失敗にする。壊れた HTML を JSON として保存しない
- `-s` — 進捗バーを出さない
- `-S` — `-s` でも失敗時はエラーを出す
- `-L` — リダイレクトを追う
- `-o FILE` — 標準出力ではなくファイルへ書く

結果：
```
（標準出力なし。成功時は /tmp/m5burner-firmware.json ができる）
```

コマンド： python3 - <<'PY' （catalog から name==StackChan-UserDemo かつ author==M5Stack の version/published_at/file を印字）

- 目的： 公式 StackChan-UserDemo の最新版名を抜く

引数：
- `-` / `<<'PY'` — 標準入力からスクリプトを読む
- `author==M5Stack` — 同名の非公式を除外する

結果：
```
V0.4 2025-12-12 dc07f852c70e01af6286c2d032f974d2.bin
...
V1.2.4 2026-04-20 3c8ffe6be0ca26375d836e10e06e3609.bin
...
V1.4.4 2026-07-13 790e3fcde496020aa7f188153b23e6f0.bin
V1.5.1 2026-07-31 746f9662f48ac465cccf49bcad941414.bin
```

コマンド： curl -L "https://m5burner-cdn.m5stack.com/firmware/746f9662f48ac465cccf49bcad941414.bin" -o firmware/official/StackChan-UserDemo-V1.5.1.bin

- 目的： 公式 1.5.1 のフルイメージを保存する

引数：
- `-L` — CDN の 302 を追う
- URL 末尾のハッシュ名 — カタログ V1.5.1 の `file` 欄
- `-o ...V1.5.1.bin` — 版がファイル名に残るようにする

結果：
```
100 12.1M  100 12.1M    0     0  15.7M      0 --:--:-- --:--:-- --:--:-- 15.6M
```

コマンド： ls -lh firmware/official/StackChan-UserDemo-V1.5.1.bin

- 目的： サイズがマージ済みイメージ相当か見る

引数：
- `-l` — 詳細
- `-h` — サイズを `13M` のように出す。マージ済みフルイメージの目安

結果：
```
-rw-rw-r-- 1 takuya takuya 13M Sep  8 22:38 StackChan-UserDemo-V1.5.1.bin
```

コマンド： od -An -tx1 -N 4 firmware/official/StackChan-UserDemo-V1.5.1.bin

- 目的： ダウンロードが ESP イメージ（先頭 e9）か確認する

引数：
- `-An` `-tx1` — アドレス無し、1 バイト十六進。実機 read-flash と同じ形式
- `-N 4` — 先頭 4 バイト。`e9` なら ESP イメージ

結果：
```
 e9 03 02 4f
```

コマンド： sha256sum firmware/official/StackChan-UserDemo-V1.5.1.bin | tee firmware/official/SHA256SUMS

- 目的： 戻し用のハッシュを残す

引数：
- `sha256sum FILE` — SHA-256 を計算する。bin は git に入れずハッシュだけ残す
- `|` — 標準出力を次へ渡す
- `tee FILE` — 画面に出しつつファイルにも書く

結果：
```
411578a2ebca2cfe3541fdc32aeddbc4703cf912a5daa7e1253f69306d6e1d87  StackChan-UserDemo-V1.5.1.bin
```

コマンド： .venv/bin/esptool --port /dev/ttyACM0 write-flash 0x0 firmware/official/StackChan-UserDemo-V1.5.1.bin

- 目的： 公式イメージへ戻す（今回は未実行）

引数：
- `--port /dev/ttyACM0` — 書き込み先
- `write-flash` — フラッシュへ書く。破壊的。本体はすでに 1.5.1 なので今回は打っていない
- `0x0` — 先頭から。マージ済みフルイメージ（ブートローダ込み）
- `...V1.5.1.bin` — 保存した公式イメージ

結果：
```
（未実行。成功時は起動ログの App version: 1.5.1 で確認する）
```

### 7. 土台ファームを文書で選ぶ（まだ焼かない）

起動ログの `AI.AGENT` / `SETUP` はスマホ・公式クラウド前提。焼くと公式 1.5.1 が消える。Wi-Fi パスワード未設定では PC 接続を確認できない。

コマンド： curl -fsSL "https://raw.githubusercontent.com/74th/websocket-control-stackchan/main/README.md" | head -n 40

- 目的： PC 頭脳型か、公式 K151 対応かを README で見る

引数：
- `-fsSL` — 失敗で止める、静か、失敗時はエラー表示、リダイレクト追従
- URL — クローンせず README 本文だけ取る
- `|` — curl の本文を次へ渡す
- `head -n 40` — 先頭 40 行。役割分担の説明は冒頭にある

結果：
```
# StackChan WebSocket Control Server
StackChanをフロントにし、メインのロジック処理をPC上のPythonで実現する
- M5Stack公式StackChan(SKU:K151)
```

コマンド： curl -fsSL "https://raw.githubusercontent.com/74th/websocket-control-stackchan/main/docs/firmware_ja.md" | grep -A2 "env:m5stack"

- 目的： 公式 K151 用の PlatformIO env 名を抜く

引数：
- `-fsSL` — 上と同じ
- URL — ファームのビルド手順
- `grep -A2` — 一致行のあと 2 行も出す
- `"env:m5stack"` — PlatformIO 環境名の接頭辞

結果：
```
- env:m5stack-cores3-m5unified: M5Stack CoreS3(SKU:K128, K128-Lite, K128-SE)
- env:m5stack-atoms3r-m5unified: M5Atom S3R(SKU:C126)とAtomic Echo Base(SKU:A149)
- env:m5stack-official-stackchan: M5Stack公式StackChan(SKU:K151)
```

コマンド： curl -fsSL "https://raw.githubusercontent.com/74th/websocket-control-stackchan/main/firmware/include/config.template.h"

- 目的： Wi-Fi とサーバ IP がビルド時埋め込みか確認する

引数：
- `-fsSL` — 上と同じ
- URL — Wi-Fi とサーバ IP がビルド時埋め込みかを見るテンプレート。実ファイル `config.h` はリポジトリに置かない

結果：
```
#define WIFI_SSID_H "__SSID__"
#define WIFI_PASSWORD_H "__PASSWORD__"
#define SERVER_HOST_H "192.168.1.179"
#define SERVER_PORT_H 8000
#define SERVER_PATH_H "/ws/stackchan"
```

見送り: 公式 1.5.1 のまま、コミュニティ stack-chan、kisaragi-mochi/stackchan-mcp。採用は 74th の `env:m5stack-official-stackchan`。フェーズ1の `SERVER_HOST_H` は `192.168.10.14`。パスワードは書かない。焼きはフェーズ1。

### 8. 成果物

| パス | 中身 |
|---|---|
| `firmware/official/StackChan-UserDemo-V1.5.1.bin` | 公式フルイメージ（git 対象外） |
| `firmware/official/SHA256SUMS` | 上記のハッシュ |
| `firmware/official/stackchan-userdemo-catalog.json` | 公式デモの版一覧 |
| `tools/99-esp32s3-usbjtag.rules` | シリアル権限用 udev |
| `.venv/` | esptool 5.4.0 / pyserial |
| `agent_reports/phase0_artifacts/flash-id.txt` | チップ情報 |
| `agent_reports/phase0_artifacts/boot.log` | 起動ログ |
| `agent_reports/phase0_artifacts/identity.json` | 識別結果の要約 |

---

## 次に必要な入力

74th ファームを焼くために、本体が乗る **2.4GHz Wi-Fi の SSID とパスワード**。ホストは `192.168.10.14:8000`、パス `/ws/stackchan`。
