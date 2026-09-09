# 反応なし（聞き取りが始まらない／空文字）

## 背景

ユーザが「反応なし」と報告した。直前のホスト（`--llm openai --tts edge`）のログは約 30 秒で `CLOCK_APPLIED` だけであり、`touch` も `pcm_start` も無かった。会話に入っていない状態で話しても、本体は時計画面のままである。

別の要因として、マイクは動いていたのに Whisper が空文字を返すケースがあった。`vad_filter=True` と平均振幅 400 未満の捨て処理が、日本語の発話を消していた。ファーム側は沈黙判定が厳しく、声とみなされないと録音が終わらなかった。

参照: `agent_reports/014_asr_empty.md`、`agent_reports/016_runaway_chat.md`、`agent_reports/017_device_speaker.md`。

## 目的

| 完了条件 | 状態 |
| --- | --- |
| 「反応なし」の原因を切り分ける | 完了。時計のまま話す／認識を捨てる／録音が終わらない |
| 1 回のタッチで会話に入り、触れ直しても時計に戻らない | 完了。戻るのは発話「時計モード」 |
| 沈黙が短くても、最大 8 秒で録音を終える | 完了。ファーム書き込み済み |
| Whisper VAD を外し、弱い声も捨てにくくする | 完了 |
| ホストを `--tts edge --llm openai` で再起動する | 完了 |

## 結論

時計画面では声に反応しない。液晶を **1 回** 触ると「話してください」になり、マイクが開く。会話中に触れ直しても時計には戻らない。戻すときは「時計モード」と言う。

録音は、声のあと約 0.8 秒の静けさ、または最大 8 秒で終わる。PC は PCM を Whisper に渡し（VAD なし）、ChatGPT の返事を本体スピーカーへ生 PCM で送る。PC では鳴らさない。

ファームを焼き、ホストを起動した。画面に日付が出ていれば接続は生きている。触れたあと、ホストログに `touch` → `pcm_start` → `pcm_end energy=` → `asr '...'` → `reply` → `tts device bytes=` → `SPEAK_DONE` が出れば反応している。

```
+---------------------------+        USB         +---------------------------+
| PC                        | -----------------> | StackChan                 |
|                           |  時計 JSON         |                           |
|  中でやること             |  listen            |  中でやること             |
|    タッチで会話に入る     |  返事の生 PCM      |    時計画面（触るまで）  |
|    弱い声も Whisper へ    |                    |    触るとマイク開始      |
|    ChatGPT → 音声にする   | <----------------- |    最大8秒で録音終了     |
|                           |  touch / PCM       |    スピーカーで返事      |
|                           |  SPEAK_DONE        |    「時計モード」で戻る  |
+---------------------------+                    +---------------------------+
```

使わなかった構成（時計のまま話す。反応しない）:

```
+---------------------------+        USB         +---------------------------+
| PC                        | -----------------> | StackChan                 |
|                           |  時計 JSON のみ    |                           |
|  中でやること             |                    |  中でやること             |
|    マイクを開かない       | <----------------- |    時計画面のまま        |
|                           |  CLOCK_APPLIED     |    声を捨てる            |
+---------------------------+                    +---------------------------+
```

未完了: 実機で今回の閾値をユーザ発話で確認する作業は、この文書の執筆時点では未実施（ホストは起動済み）。Google Calendar の本番 OAuth と Wi-Fi は対象外。

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
crw-rw-rw- 1 root plugdev 166, 0 Sep  9 22:00 /dev/ttyACM0
```

コマンド： .venv/bin/python -m py_compile host/server.py host/asr.py

- 目的： タッチ固定と ASR 閾値変更のホストが構文として通るか確認する

引数：
- `-m py_compile` — 構文チェック
- `host/server.py` — 統合ホスト
- `host/asr.py` — Whisper と振幅判定

結果：
```
（stdout なし。exit 0）
```

コマンド： .venv/bin/pytest -q host/test_asr.py host/test_intent.py host/test_clock_format.py host/test_chatfmt.py

- 目的： 振幅計算・意図・時計・折り返しの単体テストが通るか確認する

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

- 目的： 沈黙閾値を下げ、最大 8 秒で録音を終えるファームを書く

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

起動直後のシリアル断片は `agent_reports/no_response_artifacts/host_start_20260909.txt`。

変更の要点（コードを読んだ結果）:

- ホスト `on_line` の `touch`: `mode == clock` のときだけ `enter_chat()`。会話中のタッチは無視する
- ホスト ASR: `vad_filter` を外す。最短 PCM を 8000 バイト、平均振幅下限を 80 にする
- ファーム: `kSilenceAbs = 120`、`kSilenceMs = 800`、`kMaxListenMs = 8000`
