# WebSocket ポートを 8000 から 15151 に変更

## 背景

統合ホストが `0.0.0.0:8000` で落ちた。前の対応は「8000 を使っているプロセスを殺せ」だった。ユーザはポート番号を変えることを求めた。8000 は他のローカルサーバがよく使う。

## 目的

| 完了条件 | 状態 |
| --- | --- |
| ホストの既定ポートを 8000 以外にする | 完了。`15151` |
| ファームの接続先も同じ番号にする | 完了（テンプレートと手元の `config.h`） |
| README から `fuser -k 8000` を外す | 完了 |
| 既定で 15151 を待受できる | 完了 |

## 結論

WebSocket の既定は **15151** にした（StackChan SKU K151 に合わせる。8000 とぶつからない）。`host/defaults.py` の `WS_PORT` を `server.py` と `clock_server.py` が読む。本体側は `SERVER_PORT_H 15151`。USB だけのときはこのポートは使わないが、待受自体は 8000 と衝突しない。

同じコマンド（`--ws-port` なし）で `websocket ws://0.0.0.0:15151` になることを確認した。確認プロセスは止めてあり、15151 は空いている。

```
.venv/bin/python host/server.py --serial /dev/ttyACM0 --weekday en --asr whisper --tts none --llm echo
```

```
+---------------------------+     USB（主）      +---------------------------+
| PC                        | -----------------> | StackChan                 |
|                           |  時計 JSON         |                           |
|  中でやること             |                    |  中でやること             |
|    統合ホストを動かす     |                    |    USB で JSON を受ける   |
|    待受は 15151           |                    |    液晶に日時を描く       |
+---------------------------+                    +---------------------------+

Wi-Fi（未実施）

+---------------------------+     Wi-Fi 点線     +---------------------------+
| PC                        | - - - - - - - - -> | StackChan                 |
|                           |  ws 15151          |                           |
|  中でやること             |  （未実施）        |  中でやること             |
|    同じホストが 15151     |                    |    ファームの接続先も     |
|    で待つ                 |                    |    15151                  |
+---------------------------+                    +---------------------------+
```

## 詳細

コマンド： ss -ltnp | grep -E ':8000|:15151'

- 目的： 変更前に 8000 と 15151 の待受有無を見る

引数：
- `-l` — LISTEN だけ
- `-t` — TCP
- `-n` — 名前解決しない
- `-p` — プロセスを出す
- パイプ `grep -E ':8000|:15151'` — 旧ポートと新ポート

結果：
```
neither 8000 nor 15151 listening
```

コマンド： .venv/bin/python -c 'import sys; sys.path.insert(0,"host"); from defaults import WS_PORT; print(WS_PORT)'

- 目的： ホストの既定ポートが 15151 か確認する

引数：
- `-c` — `defaults.WS_PORT` を表示する短い式
- `sys.path.insert(0,"host")` — `host/` をモジュール探索に入れる

結果：
```
15151
```

コマンド： .venv/bin/python host/server.py --help

- 目的： `--ws-port` のヘルプが新既定を出すか確認する

引数：
- `host/server.py` — 統合ホスト
- `--help` — 引数説明を出す
- パイプ `grep -A1 ws-port` — ポートの行だけ残す

結果：
```
                 [--ws-host WS_HOST] [--ws-port WS_PORT]
                 [--asr {whisper,none}] [--whisper-model WHISPER_MODEL]
--
  --ws-port WS_PORT     WebSocket port (default 15151). 0 disables it (USB
                        serial only).
```

コマンド： .venv/bin/pytest -q host/test_defaults.py host/test_clock_format.py

- 目的： 既定ポートのテストと時計フォーマットが通るか確認する

引数：
- `-q` — 短い出力
- `host/test_defaults.py` — `WS_PORT == 15151` かつ 8000 ではない
- `host/test_clock_format.py` — 時計3行
- 事前に `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` — ROS プラグインを読まない（この実行では明示）

結果：
```
....                                                                     [100%]
4 passed in 0.01s
```

コマンド： .venv/bin/python host/server.py --asr none --tts none --llm echo

- 目的： `--ws-port` を付けなくても 15151 で待受するか確認する

引数：
- `host/server.py` — 統合ホスト
- `--asr none` — Whisper を読まず起動を短くする
- `--tts none` — 音声合成しない
- `--llm echo` — LLM の代わりにエコーする
- `--serial` なし — 待受だけ見る

結果：
```
websocket ws://0.0.0.0:15151
```

コマンド： ss -ltnp | grep ':15151'

- 目的： 実際に 15151 が LISTEN か確認する

引数：
- `-l` — LISTEN だけ
- `-t` — TCP
- `-n` — 名前解決しない
- `-p` — プロセスを出す
- パイプ `grep ':15151'` — 新ポートだけ

結果：
```
LISTEN 0      100                        0.0.0.0:15151      0.0.0.0:*    users:(("python",pid=163917,fd=8))
```

確認後にこのプロセスは止めた。15151 は空いている。
