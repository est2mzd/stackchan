# ChatGPT 会話ホストの起動

## 背景

ユーザは echo の復唱ではなく、ChatGPT で答えてスピーカーで鳴らす起動を求めた。`host/.env` に API キーがある。既定の `--llm-base-url` が Ollama 向け `11434` だと、`--llm openai` でもローカルへ POST してしまう。

## 目的

| 完了条件 | 状態 |
| --- | --- |
| OpenAI の API がキー付きで応答する | 完了（キーは書かない） |
| openai の接続先を api.openai.com にする | 完了 |
| `--llm openai --tts edge` でホストがシリアル待受する | 完了。プロセスは起動したまま |

## 結論

OpenAI へ短い質問を送り `2` が返った。続けて次でホストを起動し、`websocket ws://0.0.0.0:15151` と `CLOCK_APPLIED` を確認した。このプロセスは止めていない。

```
.venv/bin/python host/server.py --serial /dev/ttyACM0 --weekday en --asr whisper --tts edge --llm openai
```

液晶に触れて会話モードにし、話す。文字は画面、返事は ChatGPT、音声はスピーカー。キーはレポートに書かない。

```
+---------------------------+        USB         +---------------------------+
| PC                        | <----------------- | StackChan                 |
|                           |  マイクの音        |                           |
|  中でやること             |                    |  中でやること             |
|    音声を文字にする       | -----------------> |    液晶に返事             |
|    ChatGPT に聞く         |  返事の文字と音声  |    スピーカーで鳴らす     |
+---------------------------+                    +---------------------------+
```

## 詳細

コマンド： .venv/bin/pytest -q host/test_llm.py

- 目的： openai が Ollama の 11434 を使わないことを確認する

引数：
- `-q` — 短い出力
- `host/test_llm.py` — 接続先の単体テスト
- 事前に `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`

結果：
```
...                                                                      [100%]
3 passed in 0.06s
```

コマンド： .venv/bin/python -  （ホスト上の短い OpenAI 呼び出し）

- 目的： ローカル設定のキーで ChatGPT が返答するか確認する

引数：
- 標準入力のスクリプト — `complete(..., "openai", ...)` に「1足す1は？」を渡す
- キーは `host/.env` から読む。標準出力にキーは出さない

結果：
```
openai_ok 2
```

コマンド： .venv/bin/python host/server.py --serial /dev/ttyACM0 --weekday en --asr whisper --tts edge --llm openai

- 目的： 実機向けに ChatGPT と TTS 付きホストを起動する

引数：
- `--serial /dev/ttyACM0` — USB
- `--weekday en` — 曜日英語
- `--asr whisper` — 音声認識
- `--tts edge` — スピーカー用の音声合成
- `--llm openai` — ChatGPT

結果：
```
serial opened /dev/ttyACM0
websocket ws://0.0.0.0:15151
CLOCK_FW_READY
CLOCK_APPLIED
```

このプロセスは起動したままである。
