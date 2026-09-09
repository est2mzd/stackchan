# 1回目は認識、2回目以降が止まる件

## 背景

ログは次だった。1回目 `pcm_start` → `pcm_end bytes=146432` → `asr 'こんにちは'` → `reply`。そのあと `SPEAK_DONE` が来ず、タッチで時計に戻り、`SPEAK_DONE timeout` が出た。2回目の `pcm_start` は無い。

## 目的

| 完了条件 | 状態 |
| --- | --- |
| 1回目のあとにマイクが再開する | コード修正して焼いた |
| 再生中の「聞け」を捨てない | 完了。聞けは再生を打ち切ってマイクを開く |
| ホスト再起動 | 完了 |

## 結論

1回目の認識は成功している。止まったのはそのあと、返事の音声を送っているあいだ本体が「再生中」のまま残り、次の「聞け」を無視したためである。時計に戻っても再生フラグを消していなかった。

「聞け」と時計への切替は、再生を必ず止めてからマイクを開く。返事の音声が 8 秒以内に終わらなければ打ち切って聞く。ホストは再起動済み。液晶に触れて、2回続けて話して確認する。2回目にも `pcm_start` が出れば再開できている。

```
+---------------------------+        USB         +---------------------------+
| PC                        | -----------------> | StackChan                 |
|                           |  返事の音声        |                           |
|  中でやること             |  聞け              |  中でやること             |
|    1回目を文字にする      |                    |    再生中でも聞けが来たら |
|    返事を鳴らす           | <----------------- |    再生を止めて録る       |
|    終わらなければ切る     |  2回目の PCM       |                           |
+---------------------------+                    +---------------------------+
```

## 詳細

コマンド： （ログ確認）ホスト出力

- 目的： 2回目に pcm_start が無いか確認する

引数： なし

結果：
```
pcm_start
pcm_end bytes=146432 reason=stop
asr 'こんにちは'
reply 'こんにちは！いかがですか？'
touch
CLOCK_APPLIED
SPEAK_DONE timeout
```

コマンド： ../../.venv/bin/pio run -e m5stack-cores3 -t upload --upload-port /dev/ttyACM0

- 目的： 聞けで再生を打ち切るファームを書く

引数：
- `-e m5stack-cores3` — CoreS3 向け
- `-t upload` — 書き込み
- `--upload-port /dev/ttyACM0` — かかと側 USB
- 作業ディレクトリ — `/home/takuya/work/stackchan/firmware/clock_ws`

結果：
```
Hash of data verified.
Hard resetting via RTS pin...
========================= [SUCCESS] Took 15.94 seconds =========================
```

コマンド： .venv/bin/python host/server.py --serial /dev/ttyACM0 --weekday en --asr whisper --tts edge --llm openai

- 目的： 修正後のホストを起動する

引数：
- `--serial /dev/ttyACM0` — USB
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
