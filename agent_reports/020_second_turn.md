# 2回目以降のフリーズと音声なし

## 背景

ユーザが「2回目以降がフリーズ、かつ、音声が出ない」と報告した。ホストログは 1 回目 `asr 'こんにちは'` → `reply` → `tts device bytes=148224` のあと `SPEAK_DONE` が来ず、`SPEAK_DONE timeout` で終わっていた。そのあいだに `touch` がある。

参照: `agent_reports/015_second_listen.md`、`agent_reports/019_freeze.md`。失敗ログ: `agent_reports/second_turn_artifacts/host_before_fix_20260909.txt`。

## 目的

| 完了条件 | 状態 |
| --- | --- |
| 返事の PCM を受信しながらスピーカーで鳴らす | 完了。3 面の小さなバッファ |
| `SPEAK_DONE` が再生後に出る | コードと書き込み済み。実機の声は未確認 |
| 再生中の「聞け」で再生を捨てない | 完了。鳴り終わってからマイク |
| 2 回目の録音が始まる | 完了条件はログに 2 回目の `pcm_start`。執筆時点は起動のみ |
| ファーム書き込みとホスト再起動 | 完了 |

## 結論

音声が出なかったのは、返事の PCM（約 148 KB）を内部 RAM に全部溜めてから鳴らそうとし、そのあいだ `loop` の `delay(5)` で USB 受信が遅れ、ホストの待ち（約 8 秒）が先に切れたためである。再生が始まらないのでスピーカーは沈黙する。切れたあとホストが送る「idle / 聞け」が、まだバイナリ待ちの本体に音声バイトとして食われ、2 回目が止まる。

本体は 1024 サンプルずつ受信と同時に再生する。再生中はタッチを送らない。マイクとスピーカーの切替に 30 ms 空ける。ホストは PCM を 2048 バイトずつ書き、`SPEAK_DONE` を最大 12 秒以上待つ。PC では鳴らさない。

ファームを焼き、ホストを起動した。液晶に触れて 2 回話す。1 回目のあと本体から声が出て、ログに `SPEAK_DONE` と 2 回目の `pcm_start` が出れば直っている。

```
+---------------------------+        USB         +---------------------------+
| PC                        | -----------------> | StackChan                 |
|                           |  speak_start       |                           |
|  中でやること             |  生 PCM を分割     |  中でやること             |
|    返事を音声にする       |                    |    受信しながら再生      |
|    SPEAK_DONE まで待つ    | <----------------- |    鳴り終わってから録音  |
|    それからまた聞け       |  SPEAK_DONE        |    スピーカーで返事      |
+---------------------------+                    +---------------------------+
```

使わなかった構成（全部溜めてから再生し、待ちが切れる）:

```
+---------------------------+        USB         +---------------------------+
| PC                        | -----------------> | StackChan                 |
|                           |  148KB 一括        |                           |
|  中でやること             |                    |  中でやること             |
|    8秒で打ち切る          | <----------------- |    delay(5) で受信遅れ   |
|    idle を送る            |  来ない SPEAK_DONE |    再生前に打ち切られる  |
+---------------------------+                    +---------------------------+
```

未完了: ユーザ発話でのスピーカー確認と 2 回目の `pcm_start` 確認（ホストは起動済み）。

## 詳細

コマンド： （ログ確認）ホスト出力

- 目的： 1 回目のあと SPEAK_DONE が無いか確認する

引数： なし

結果：
```
asr 'こんにちは'
reply 'こんにちは！どんなことをお話ししましょうか？'
tts device bytes=148224
touch
SPEAK_DONE timeout
```

コマンド： lsusb

- 目的： PC が本体を USB デバイスとして認識しているか確認する

引数： なし

結果：
```
Bus 003 Device 010: ID 303a:1001 Espressif USB JTAG/serial debug unit
```

コマンド： .venv/bin/python -m py_compile host/server.py

- 目的： PCM 分割送信のホストが構文として通るか確認する

引数：
- `-m py_compile` — 構文チェック
- `host/server.py` — 統合ホスト

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

- 目的： 受信しながら再生するファームを書く

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
