# ざーーー（ホワイトノイズ）

## 背景

返事の PCM はホストから届き `SPEAK_DONE` も出るが、スピーカーは言語ではなく「ざーーー」だけだった。`agent_reports/021_static.md` と `022_bug_catalog.md` の未完了。

CoreS3 のアンプ AW88298 は I2S を「16 bit × 2」（ステレオ）で受ける。本体コードは `spk.stereo = false` で I2S をモノラルにしていた。クロックの形がアンプと食い違い、波形が乱数に聞こえる。

## 目的

| 完了条件 | 状態 |
| --- | --- |
| I2S をアンプと同じステレオにする | 完了。`spk.stereo = true` |
| 再生データはモノラル 16 kHz のまま | 完了。`playRaw(..., false)` |
| PSRAM を直接 playRaw しない | 完了。内部 RAM の 3 面にコピー |
| ファーム書き込みとホスト再起動 | 完了 |

## 結論

ざーーーは、アンプがステレオ I2S を期待しているのに、装置をモノラルにしていたためである。データ（16 kHz モノラル）はそのまま送り、I2S 出力だけステレオにする。ライブラリが左右に同じサンプルを載せる。再生は内部 RAM の 1024 サンプル×3 面で、使い終わるまで上書きしない。

ファームを焼き、ホストを起動した。液晶に触れて話す。返事が日本語として聞こえるかが確認条件である。PC では鳴らさない。

```
+---------------------------+        USB         +---------------------------+
| PC                        | -----------------> | StackChan                 |
|                           |  16kHz モノ PCM    |                           |
|  中でやること             |                    |  中でやること             |
|    返事を PCM にする      |                    |    I2S はステレオ        |
|                           | <----------------- |    内部RAMから再生       |
|                           |  SPEAK_DONE        |    左右に同じ波形        |
+---------------------------+                    +---------------------------+
```

使わなかった構成（I2S モノラル。ざーーーになる）:

```
+---------------------------+        USB         +---------------------------+
| PC                        | -----------------> | StackChan                 |
|                           |  16kHz モノ PCM    |                           |
|  中でやること             |                    |  中でやること             |
|    同じ PCM を送る        |                    |    I2S をモノラルにする  |
|                           | <----------------- |    AW88298 と食い違う    |
|                           |  SPEAK_DONE        |    ざーーーと鳴る        |
+---------------------------+                    +---------------------------+
```

未完了: ユーザが日本語として聞こえるかの確認（ホストは起動済み）。

## 詳細

コマンド： sed -n '219,280p' firmware/clock_ws/src/main.cpp

- 目的： ステレオ I2S と内部 RAM 再生のコードを確認する

引数：
- `-n '219,280p'`
- `firmware/clock_ws/src/main.cpp`

結果：
```
spk.sample_rate = kSpkHwRate;  // 48000
spk.stereo = true;
...
M5.Speaker.playRaw(play_int[ch], n, kSampleRate, false, 1, ch, false);
```

第 4 引数 `false` は PCM がモノラルであること。装置の `stereo = true` とは別である。

コマンド： .venv/bin/pytest -q host/test_asr.py host/test_clock_format.py

- 目的： ホスト単体テストがまだ通るか確認する

引数：
- `-q` — 短い出力
- `host/test_asr.py`
- `host/test_clock_format.py`

結果：
```
.....                                                                    [100%]
5 passed in 0.01s
```

コマンド： ../../.venv/bin/pio run -e m5stack-cores3 -t upload --upload-port /dev/ttyACM0

- 目的： ステレオ I2S のファームを書く

引数：
- `-e m5stack-cores3` — CoreS3 向け
- `-t upload` — 書き込み
- `--upload-port /dev/ttyACM0` — かかと側 USB
- 作業ディレクトリ — `/home/takuya/work/stackchan/firmware/clock_ws`

結果：
```
Hash of data verified.
Hard resetting via RTS pin...
========================= [SUCCESS] Took 16.45 seconds =========================
```

コマンド： .venv/bin/python host/server.py --serial /dev/ttyACM0 --weekday en --asr whisper --tts edge --llm openai

- 目的： 修正後のホストを起動し、時計が届くか確認する

引数：
- `--serial /dev/ttyACM0` — USB
- `--weekday en` — 曜日英語
- `--asr whisper` — 音声認識
- `--tts edge` — 返事の PCM
- `--llm openai` — ChatGPT

結果：
```
serial opened /dev/ttyACM0
websocket ws://0.0.0.0:15151
CLOCK_FW_READY
CLOCK_APPLIED
```
