# 会話の文字切れと2回目フリーズ

## 背景

ChatGPT 会話で、返事の文字が液晶からはみ出して切れた。1回目は答えるが、2回目は止まる。ホストログは `reply 'こんにちは！どうぞよろしくお願いします。'` のあと `SPEAK_DONE` が無く、その後タッチで時計に戻っていた。

## 目的

| 完了条件 | 状態 |
| --- | --- |
| 会話文を画面幅に折り返す | 完了。12字×最大4行、左寄せ |
| 再生中に本体のループが止まらない | 完了。再生待ちを `loop` に移した |
| 再生が終わるまで次の「聞け」を捨てない | 完了。ホストは `SPEAK_DONE` 待ち。本体は再生中の listen をキューする |
| 実機に書いてホストを再起動する | 完了 |

## 結論

文字切れは、中央寄せの1行に長い日本語を載せていたためである。12字で折り返し、小さいフォントで左から描く。

2回目の停止は、スピーカー再生のあいだ本体が `delay` で止まり、その間に来た「聞け」を捨てていたためである。再生は待たずに開始し、鳴り終わってから `SPEAK_DONE` を出す。ホストはそれを受けてから次の録音を始める。返事は2文・各20字以内に短くした。

ホストは再起動済み。液晶に触れて、2回続けて話して確認する。ログに `SPEAK_DONE` が出れば再生完了である。

```
+---------------------------+        USB         +---------------------------+
| PC                        | -----------------> | StackChan                 |
|                           |  折り返した文字    |                           |
|  中でやること             |  返事の音声        |  中でやること             |
|    ChatGPT に聞く         |                    |    4行で描く              |
|    SPEAK_DONE まで待つ    | <----------------- |    再生中もシリアルを読む |
|    それからまた聞く       |  鳴り終わった      |    終わってからマイク     |
+---------------------------+                    +---------------------------+
```

## 詳細

コマンド： .venv/bin/pytest -q host/test_chatfmt.py host/test_llm.py

- 目的： 折り返しと LLM 接続先のテストが通るか確認する

引数：
- `-q` — 短い出力
- `host/test_chatfmt.py` — 12字折り返し
- `host/test_llm.py` — OpenAI の URL
- 事前に `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`

結果：
```
........                                                                 [100%]
8 passed in 0.06s
```

コマンド： ../../.venv/bin/pio run -e m5stack-cores3 -t upload --upload-port /dev/ttyACM0

- 目的： 折り返し描画と非同期再生のファームを本体に書く

引数：
- `-e m5stack-cores3` — CoreS3 向け
- `-t upload` — 書き込み
- `--upload-port /dev/ttyACM0` — かかと側 USB
- 作業ディレクトリ — `/home/takuya/work/stackchan/firmware/clock_ws`

結果：
```
Hash of data verified.
Hard resetting via RTS pin...
========================= [SUCCESS] Took 15.96 seconds =========================
```

コマンド： .venv/bin/python host/server.py --serial /dev/ttyACM0 --weekday en --asr whisper --tts edge --llm openai

- 目的： 修正後の ChatGPT ホストを起動する

引数：
- `--serial /dev/ttyACM0` — USB
- `--weekday en` — 曜日英語
- `--asr whisper` — 音声認識
- `--tts edge` — スピーカー
- `--llm openai` — ChatGPT

結果：
```
serial opened /dev/ttyACM0
websocket ws://0.0.0.0:15151
CLOCK_APPLIED
```

このプロセスは起動したままである。
