# 画面フリーズ（録音中に止まる）

## 背景

ユーザが「フリーズ」と報告した。ホストログは 90 秒以上 `CLOCK_APPLIED` だけで、`touch` / `pcm_start` が無かった。触っても `wasClicked` を取りこぼすと時計のまま動かない。触れて録音に入ると、マイク PCM を 1 秒に何十回も JSON で USB に流し、本体の `loop` が `Serial.println` で塞がって画面が止まる。

参照: `agent_reports/011_thinking_freeze.md`、`agent_reports/013_chat_wrap_speak.md`、`agent_reports/018_no_response.md`。

## 目的

| 完了条件 | 状態 |
| --- | --- |
| タッチを取りこぼしにくくする | 完了。押しているあいだに 1 回送る |
| 録音中に USB を JSON で埋めない | 完了。本体メモリに溜めてから生 PCM |
| 録音中も画面が動いて見える | 完了。「聞いています」と残り秒 |
| Whisper 待ちを「考え中」と出す | 完了 |
| ファーム書き込みとホスト再起動 | 完了 |

## 結論

止まり方は二つある。液晶のタップがホストに届かないことと、届いたあとにマイク JSON が USB を塞いで描画が止まることである。

タップは押した瞬間に 1 回送る。録音は最大 4 秒、本体の PSRAM に溜め、終わってから生 PCM をまとめて送る。録音中は「聞いています」と残り秒を描く。認識のあいだは「考え中」。PC では鳴らさない。

ファームを焼き、ホストを起動した。顔の液晶を触ると秒が減る。ログに `touch` → `pcm_start bytes=` → `pcm_end` → `asr` → `reply` → `SPEAK_DONE` が出れば止まっていない。

```
+---------------------------+        USB         +---------------------------+
| PC                        | -----------------> | StackChan                 |
|                           |  時計 JSON / 聞け  |                           |
|  中でやること             |  返事の生 PCM      |  中でやること             |
|    シリアルは同時に書かない|                    |    触れたら録音（最大4秒）|
|    録音後にまとめて受ける | <----------------- |    画面に残り秒          |
|    考え中を出してから認識 |  touch             |    終わってから生 PCM    |
|                           |  生 PCM 一括       |    スピーカーで返事      |
+---------------------------+                    +---------------------------+
```

使わなかった構成（録音中に JSON を流し続けて止まる）:

```
+---------------------------+        USB         +---------------------------+
| PC                        | -----------------> | StackChan                 |
|                           |  時計と聞け        |                           |
|  中でやること             |                    |  中でやること             |
|    1秒に何十本も PCM JSON | <----------------- |    Serial 送信で loop 停止|
|    を読む                 |  PCM JSON 連打     |    画面が「話してください」|
+---------------------------+                    +---------------------------+
```

未完了: この文書の執筆時点では、ユーザ発話での実機確認は未実施（ホストは起動済み）。

## 詳細

コマンド： lsusb

- 目的： PC が本体を USB デバイスとして認識しているか確認する

引数： なし

結果：
```
Bus 003 Device 010: ID 303a:1001 Espressif USB JTAG/serial debug unit
```

コマンド： ls -l /dev/ttyACM* /dev/ttyUSB* 2>/dev/null

- 目的： シリアルの実名と権限を見る

引数：
- `-l` — 権限・所有者・リンク先を出す
- `/dev/ttyACM*` — ESP32-S3 内蔵 USB シリアルの名前
- `/dev/ttyUSB*` — USB-UART 変換チップの名前。無い機体もある
- `2>/dev/null` — グロブ 0 件のエラーメッセージを捨てる

結果：
```
crw-rw-rw- 1 root plugdev 166, 0 Sep  9 22:06 /dev/ttyACM0
```

コマンド： .venv/bin/python -m py_compile host/server.py host/asr.py

- 目的： 生 PCM 受信とシリアル排他のホストが構文として通るか確認する

引数：
- `-m py_compile` — 構文チェック
- `host/server.py` — 統合ホスト
- `host/asr.py` — Whisper

結果：
```
（stdout なし。exit 0）
```

コマンド： .venv/bin/pytest -q host/test_asr.py host/test_intent.py host/test_clock_format.py host/test_chatfmt.py

- 目的： 振幅・意図・時計・折り返しの単体テストが通るか確認する

引数：
- `-q` — 短い出力
- `host/test_asr.py` — `pcm_mean_abs`
- `host/test_intent.py` — 「時計モード」など
- `host/test_clock_format.py` — 日時3行
- `host/test_chatfmt.py` — 画面折り返し

結果：
```
.............                                                            [100%]
13 passed in 0.02s
```

コマンド： ../../.venv/bin/pio run -e m5stack-cores3 -t upload --upload-port /dev/ttyACM0

- 目的： 録音をメモリに溜め、タッチを押し検出にするファームを書く

引数：
- `-e m5stack-cores3` — CoreS3 向け
- `-t upload` — 書き込み
- `--upload-port /dev/ttyACM0` — かかと側 USB
- 作業ディレクトリ — `/home/takuya/work/stackchan/firmware/clock_ws`

結果：
```
Hash of data verified.
Hard resetting via RTS pin...
========================= [SUCCESS] Took 15.85 seconds =========================
```

コマンド： .venv/bin/python host/server.py --serial /dev/ttyACM0 --weekday en --asr whisper --tts edge --llm openai

- 目的： 修正後のホストを USB で起動し、時計 JSON が本体に届くか確認する

引数：
- `--serial /dev/ttyACM0` — USB
- `--weekday en` — 曜日を英語
- `--asr whisper` — 音声認識
- `--tts edge` — 返事を音声データにする（再生は本体）
- `--llm openai` — ChatGPT

結果：
```
serial opened /dev/ttyACM0
websocket ws://0.0.0.0:15151
CLOCK_FW_READY
CLOCK_APPLIED
```

起動直後のシリアル断片は `agent_reports/freeze_artifacts/host_start_20260909.txt`。
