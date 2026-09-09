# 2回目失敗・二重タッチ初期化・勝手に文字が出る件

## 背景

1回目は `asr '今日の電気は?'` まで成功。その直後 `SPEAK_DONE timeout` と空の `pcm_end bytes=97280` が繰り返され、Whisper が無音を `キャンディング` や `この動画は動画をご視聴してください。` と誤って文字にし、ChatGPT が勝手に返事を描いた。会話中に `CLOCK_TIMEOUT` も出た。ユーザは2回タッチしないと戻せなかった。

## 目的

| 完了条件 | 状態 |
| --- | --- |
| 返事の音声 PCM でシリアルが詰まらない | 完了。USB では TTS を送らない |
| 無音を ChatGPT に渡さない | 完了。声が無いと録音を終わらせない。小さすぎる音は ASR しない |
| 会話中に「未接続」へ落ちない | 完了。タイムアウトは時計画面だけ |
| ホスト再起動 | 完了 |

## 結論

暴走は ChatGPT ではなく、無音を Whisper が誤認識し、すぐまた聞くループだった。2回タッチは、音声 PCM でシリアルが詰まり 2.5 秒で「未接続」になったあとの切替である。

USB では返事は画面だけにする（スピーカー用 PCM は送らない）。声を検出してから約 1.2 秒静かになったときだけ録音を終わる。時計画面以外は「未接続」にしない。

ホストは再起動済み。液晶に触れて話し、返事は画面を見る。2回目も同じように話せるはずである。

```
+---------------------------+        USB         +---------------------------+
| PC                        | <----------------- | StackChan                 |
|                           |  声があるときだけ  |                           |
|  中でやること             |  マイク PCM        |  中でやること             |
|    小さい音は無視         |                    |    声のあと静かにしたら   |
|    ChatGPT の返事を文字に | -----------------> |    録音を終わる           |
|    音声 PCM は送らない    |  返事の文字        |    液晶に描く             |
+---------------------------+                    +---------------------------+
```

## 詳細

コマンド： .venv/bin/pytest -q host/test_asr.py host/test_chatfmt.py

- 目的： 無音判定と折り返しのテストが通るか確認する

引数：
- `-q` — 短い出力
- `host/test_asr.py` — PCM 振幅
- `host/test_chatfmt.py` — 画面の行
- 事前に `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`

結果：
```
.......                                                                  [100%]
7 passed in 0.01s
```

コマンド： ../../.venv/bin/pio run -e m5stack-cores3 -t upload --upload-port /dev/ttyACM0

- 目的： 声検出してから録音終了、会話で未接続にしないファームを書く

引数：
- `-e m5stack-cores3` — CoreS3 向け
- `-t upload` — 書き込み
- `--upload-port /dev/ttyACM0` — かかと側 USB
- 作業ディレクトリ — `/home/takuya/work/stackchan/firmware/clock_ws`

結果：
```
Hash of data verified.
Hard resetting via RTS pin...
========================= [SUCCESS] Took 15.84 seconds =========================
```

コマンド： .venv/bin/python host/server.py --serial /dev/ttyACM0 --weekday en --asr whisper --tts none --llm openai

- 目的： USB に音声 PCM を流さない ChatGPT ホストを起動する

引数：
- `--serial /dev/ttyACM0` — USB
- `--asr whisper` — 音声認識
- `--tts none` — スピーカー用 PCM を作らない
- `--llm openai` — ChatGPT

結果：
```
serial opened /dev/ttyACM0
websocket ws://0.0.0.0:15151
CLOCK_APPLIED
```

このプロセスは起動したままである。
