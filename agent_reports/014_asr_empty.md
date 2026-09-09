# 音声認識が動かない件

## 背景

会話モードにしても文字にならない。ホストログは `pcm_end bytes=0` と `asr ''` が繰り返されていた。以前は同じマイク経路で数万バイトの PCM が届いていた。

## 目的

| 完了条件 | 状態 |
| --- | --- |
| 無音終了なのに PCM が 0 バイトになる原因を特定する | 完了。長いシリアル行を送信前に捨てていた |
| マイク PCM を捨てないファームを焼く | 完了 |
| ホストを再起動する | 完了 |

## 結論

音声認識本体ではなく、**マイク波形を USB で送る直前に捨てていた**。USB の送信バッファが PCM 1行より小さいので、`availableForWrite` 判定だと波形は全部落ち、終了だけが届く。Whisper には空データしか来ない。

その判定を外した。スピーカーを使っていないときは I2S を外さない。ホストは再起動済み。液晶に触れて話し、ログに `pcm_start` と `pcm_end bytes=` が 0 以外で出れば録音は届いている。

```
+---------------------------+        USB         +---------------------------+
| PC                        | <----------------- | StackChan                 |
|                           |  マイク PCM        |                           |
|  中でやること             |  （捨てない）      |  中でやること             |
|    Whisper で文字にする   |                    |    録った波形を送る       |
+---------------------------+                    +---------------------------+
```

## 詳細

コマンド： （ログ確認）ホスト出力 `pcm_end bytes=0`

- 目的： 認識失敗が Whisper か、録音が届いていないかを分ける

引数： なし

結果：
```
touch
pcm_end bytes=0 reason=stop
asr ''
pcm_end bytes=0 reason=stop
asr ''
```

コマンド： ../../.venv/bin/pio run -e m5stack-cores3 -t upload --upload-port /dev/ttyACM0

- 目的： PCM を捨てないファームを本体に書く

引数：
- `-e m5stack-cores3` — CoreS3 向け
- `-t upload` — 書き込み
- `--upload-port /dev/ttyACM0` — かかと側 USB
- 作業ディレクトリ — `/home/takuya/work/stackchan/firmware/clock_ws`

結果：
```
Hash of data verified.
Hard resetting via RTS pin...
========================= [SUCCESS] Took 15.70 seconds =========================
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
