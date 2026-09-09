# スピーカーがザザッと鳴る件

## 背景

音は出るようになったが、言語にならずザザッというノイズだけだった。ホストログでは `tts device bytes=` のあと `SPEAK_DONE` が出ており、2 回目の録音も始まっていた。経路は生きているが、波形の渡し方が壊れていた。

参照: `agent_reports/020_second_turn.md`。

## 目的

| 完了条件 | 状態 |
| --- | --- |
| 再生中にバッファを上書きしない | 完了。PSRAM に全部入れてから 1 回再生 |
| スピーカー切替中に PCM を欠かさない | 完了。ヘッダのあと 80 ms 待ってから送る |
| ハードウェア 48 kHz、データ 16 kHz | 完了。ライブラリが変換する |
| ファーム書き込みとホスト再起動 | 完了 |

## 結論

ザザッは、3 面の小さなバッファを再生中に使い回していたことと、マイクからスピーカーへ切り替える 50 ms のあいだに PCM が欠けて 16 bit の組がずれたことである。欠けた PCM は乱数に近く、言葉に聞こえない。

本体は返事の PCM を PSRAM に最後まで受けてから、一度だけ再生する。PC は `speak_start` のあと 80 ms 空けてから PCM を送る。スピーカー装置は 48 kHz、データは 16 kHz。PC では鳴らさない。

ファームを焼き、ホストを起動した。液晶に触れて話す。返事が日本語として聞こえるかが確認条件である。

```
+---------------------------+        USB         +---------------------------+
| PC                        | -----------------> | StackChan                 |
|                           |  speak_start       |                           |
|  中でやること             |  80ms 空ける       |  中でやること             |
|    返事を 16kHz PCM にする|  生 PCM            |    マイクを止めてスピーカ|
|    終わってから送れ       |                    |    PSRAM に全部貯める    |
|                           | <----------------- |    一度だけ再生          |
|                           |  SPEAK_DONE        |    日本語として鳴る      |
+---------------------------+                    +---------------------------+
```

使わなかった構成（受信しながら 3 面バッファを上書き）:

```
+---------------------------+        USB         +---------------------------+
| PC                        | -----------------> | StackChan                 |
|                           |  PCM を流し続ける  |                           |
|  中でやること             |                    |  中でやること             |
|    ヘッダの直後に送る     |                    |    再生中の面を上書き    |
|                           | <----------------- |    欠けてバイトがずれる  |
|                           |  SPEAK_DONE        |    ザザッと鳴る          |
+---------------------------+                    +---------------------------+
```

未完了: ユーザが日本語として聞こえるかの確認（ホストは起動済み）。

## 詳細

コマンド： （ログ確認）ホスト出力

- 目的： 音が出た会話で SPEAK_DONE まで届いているか確認する

引数： なし

結果：
```
asr 'こんにちは'
reply 'こんにちは！どうぞよろしくお願いします。'
tts device bytes=142080
SPEAK_DONE
```

コマンド： lsusb

- 目的： PC が本体を USB デバイスとして認識しているか確認する

引数： なし

結果：
```
Bus 003 Device 010: ID 303a:1001 Espressif USB JTAG/serial debug unit
```

コマンド： .venv/bin/python -m py_compile host/server.py

- 目的： ヘッダ後待ちを入れたホストが構文として通るか確認する

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

- 目的： PSRAM に貯めてから一度再生するファームを書く

引数：
- `-e m5stack-cores3` — CoreS3 向け
- `-t upload` — 書き込み
- `--upload-port /dev/ttyACM0` — かかと側 USB
- 作業ディレクトリ — `/home/takuya/work/stackchan/firmware/clock_ws`

結果：
```
Hash of data verified.
Hard resetting via RTS pin...
========================= [SUCCESS] Took 15.81 seconds =========================
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
