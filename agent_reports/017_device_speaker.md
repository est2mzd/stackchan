# 返事の声を StackChan スピーカーで鳴らす

## 背景

USB に JSON の PCM を流すとシリアルが詰まるため、一時的に TTS を止めていた。その結果スピーカーから音が出なかった。ユーザは PC 本体で鳴らすことを拒否し、StackChan のスピーカーだけを求めている。

## 目的

| 完了条件 | 状態 |
| --- | --- |
| 声を PC では鳴らさない | 完了 |
| 声を本体スピーカーへ送る | 完了。JSON ではなく生 PCM |
| ホスト再起動（`--tts edge`） | 完了 |

## 結論

PC のスピーカーは使わない。ホストは edge-tts で 16 kHz の PCM を作り、`speak_start` のあとに生バイトを USB で送る。本体はそれを受け取ってスピーカーで再生する。時計の 1 秒送信は再生中止める。

ファームを焼き、`--tts edge` でホストを起動した。液晶に触れて話す。ログに `tts device bytes=` と `SPEAK_DONE` が出れば本体で鳴っている。

```
+---------------------------+        USB         +---------------------------+
| PC                        | -----------------> | StackChan                 |
|                           |  speak_start       |                           |
|  中でやること             |  生 PCM            |  中でやること             |
|    ChatGPT の返事を        |                    |    スピーカーで鳴らす     |
|    音声データにする       | <----------------- |    液晶に文字             |
|    PC では鳴らさない      |  SPEAK_DONE        |                           |
+---------------------------+                    +---------------------------+
```

## 詳細

コマンド： .venv/bin/python -m py_compile host/server.py

- 目的： 生 PCM 送信のホストが構文として通るか確認する

引数：
- `-m py_compile` — 構文チェック
- `host/server.py` — 統合ホスト

結果：
```
（stdout なし。exit 0）
```

コマンド： ../../.venv/bin/pio run -e m5stack-cores3 -t upload --upload-port /dev/ttyACM0

- 目的： 生 PCM を受けてスピーカーで鳴らすファームを書く

引数：
- `-e m5stack-cores3` — CoreS3 向け
- `-t upload` — 書き込み
- `--upload-port /dev/ttyACM0` — かかと側 USB
- 作業ディレクトリ — `/home/takuya/work/stackchan/firmware/clock_ws`

結果：
```
Hash of data verified.
Hard resetting via RTS pin...
========================= [SUCCESS] Took 15.95 seconds =========================
```

コマンド： .venv/bin/python host/server.py --serial /dev/ttyACM0 --weekday en --asr whisper --tts edge --llm openai

- 目的： 本体スピーカー向け TTS 付きでホストを起動する

引数：
- `--serial /dev/ttyACM0` — USB
- `--asr whisper` — 音声認識
- `--tts edge` — 返事を音声データにする（再生は本体）
- `--llm openai` — ChatGPT

結果：
```
serial opened /dev/ttyACM0
websocket ws://0.0.0.0:15151
CLOCK_APPLIED
```

このプロセスは起動したままである。
