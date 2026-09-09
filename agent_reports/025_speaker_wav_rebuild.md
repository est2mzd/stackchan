# スピーカー再生経路

## 背景

業務は三つある。

- 会話
- 時計
- カレンダー読み上げ

いずれも次の分担である。

- StackChan（公式 M5Stack の卓上ロボット。SKU K151。基板は CoreS3）はマイク・液晶・スピーカー
- 頭脳は PC
- 公式スマホアプリは使わない
- 根拠は `user_directions/001_objective.md` と `agent_reports/001_plan.md`

位置づけは次のとおり。

- 時計画面は、かかとUSB（本体かかと側の USB-C）の JSON で日付・時刻・曜日を描ける
- 会話の入力（マイク PCM）と ChatGPT まではホスト側にある
- 欠けているのは会話とカレンダーの出力
- つまり PC が作った音声を本体スピーカーで聞くこと

現状は次のとおり。

- かかと側 USB-C で PC と StackChan がつながっている
- 本体プログラムは PlatformIO の自己試験（`speaker-self-test`）
- 会話用プログラムと `host/server.py` は動いていない
- ライブラリは M5Unified 0.2.21
- CoreS3 は AW88298（スピーカー用アンプ）と ES7210（マイク用 IC）を持つ
- マイクとスピーカーは同時には使えない
- シリアルを開くと ESP32-S3 は再起動する

## 目的

- PC 上の日本語テキストが、本体スピーカーから言葉として聞こえること
- そのあと、マイク → Whisper → ChatGPT → 同じ再生、へ戻すこと

## 手段

操作は次のとおり。

- PC が日本語の文を音声ファイルにする
- かかとUSBでそのファイルを本体へ送る
- 本体がマイクを止めてスピーカーを開き、`playWav` で鳴らす

この手段を選ぶ理由は次のとおり。

- 音声ファイルのヘッダに再生に必要な情報が載るので、PC と本体の解釈がずれにくい
- 送ったバイトが欠けたかどうかは検査和で分かる
- `playWav` は同梱ライブラリの再生である
- マイクとスピーカーは同時に使えない（CoreS3 の公式手順）

検算

- この操作が終わると「PC の日本語が本体から聞こえる」が真になる
- それが真だと、背景の「会話・カレンダーのスピーカー出力が欠けている」が埋まる

## 結論

- **現状**
  - 本体は自己試験
  - 会話ホストは停止
  - Step 1〜4 は完了
  - Step 5: USB で送った WAV は日本語として聞こえた。待ちも足りる
  - 送信は約 20 秒から、コマンド全体 8.32 秒まで短くした
  - Step 6 は未実施
- **次のタスク**
  - Step 6
  - 会話用プログラムを本体に書き、同じ WAV の送り方で会話の再生に戻す

```
+---------------------------+     かかとUSB      +---------------------------+
| PC                        | -----------------> | StackChan                 |
|                           |  SPEAK_BEGIN のあと|                           |
|  中でやること             |  hello.wav のバイト|  中でやること             |
|    長さと検査和を先に送る |                    |    揃ってから playWav     |
|    本体の合図で続きを送る | <----------------- |    終わったら知らせる     |
+---------------------------+     終了           +---------------------------+
```

同じ構成（いま送った）:

```
+---------------------------+        USB         +---------------------------+
| PC                        | -----------------> | StackChan                 |
|                           |  標準WAV           |                           |
|  中でやること             |                    |  中でやること             |
|    文をTTSでWAVにする     | <----------------- |    CRC一致後に playWav    |
|                           |  終了              |                           |
+---------------------------+                    +---------------------------+
```

---

## 詳細 — Step

- 各Stepの欠けを一つ足す
- 終わっていないStepの結果は、あとの合格に使わない

### Step 1 — 起動tone

背景

- 会話の出力の末端は本体スピーカーと AW88298
- そこが死んでいれば WAV も USB も無意味
- 自己試験は起動時に `M5.Speaker.tone(880, 400)` を呼ぶ
- ビープの有無は未確認

目的

- 本体スピーカーから短いビープが出ること

手段

- PC が [`tools/read_boot_tone.py`](../tools/read_boot_tone.py) を `python3` で実行する
- そのプログラムがかかとUSBのシリアル `/dev/ttyACM0` を開く
- ESP32-S3 が `rst:0x15` で再起動する
- `setup` の `M5.begin`、`setVolume(128)`、`tone(880, 400)` が走る
- プログラムは `played_ms:400` を返す
- 抜き差しと同じリセット経路で、ログが残る
- この操作を選ぶ理由: 起動時の tone だけで、アンプまでの経路が生きているかが分かる

検算

- シリアルオープン → リセット → tone → 400 ms 実行＝プログラム側の目的
- スピーカーからビープが出るかが残る観測
- ビープが出れば、背景の「アンプまで生きているか未確認」が埋まる

状態

- ログ取得済み
- 耳は聞こえた（短いビープ）

実践方法

- 使うファイルは [`tools/read_boot_tone.py`](../tools/read_boot_tone.py)
- データの送り方: 音声は送らない。シリアルを開くだけで本体がリセットされ、起動 tone が鳴る

```
# PCで、本体をリセットして起動toneのJSONを読むために、シリアル受信のPythonを実行する（WAVは送らない）
python3 tools/read_boot_tone.py
```

結果

- 起動ログに `tone` の JSON が出た
- 耳は短いビープが聞こえた

結果詳細

```
rst:0x15 (USB_UART_CHIP_RESET)
{"type":"SELF_TEST","phase":"boot"}
{"type":"SELF_TEST","phase":"tone","playWav":true,"played_ms":400}
```

全文: [`agent_reports/speaker_wav_rebuild_artifacts/step1_tone.txt`](speaker_wav_rebuild_artifacts/step1_tone.txt)

### Step 2 — 録音再生

背景

- 会話はマイクで録ってからスピーカーで返す
- CoreS3 は両方を同時に使えない
- 自己試験は画面タッチ1回目で 2 秒 `Mic.record` のあと `playRaw` する

目的

- いま話した声が、本体スピーカーから返って聞こえること
- 会話に使える大きさであること

手段

- 1回目: 利用者が画面を1回だけタッチする
- 液晶は tone のあと `1 tone` / `played` / `touch = rec 2s`
- タッチすると液晶が `2 rec 2s` / `speak now` になる
- そのあいだに2秒話す
- 本体だけがマイク→メモリ→`Mic.end`→`Speaker.begin`→`playRaw(..., 16000, false)`→`Speaker.end` する
- 処理は [`firmware/clock_ws/src/speaker_self_test.cpp`](../firmware/clock_ws/src/speaker_self_test.cpp) の `playRec`
- 1回目の結果: 声は返ったが小さかった
- 2回目: `M5.Speaker.setVolume` を 128 から 255 にする（範囲は 0〜255）
- PC が PlatformIO の `speaker-self-test` をかかとUSBへ書く
- 書き込み後はリセットされ、起動 tone のあと、画面を1回だけタッチして2秒話す
- 2回目のタッチは Step 3 なので、いまは1回だけ
- この操作を選ぶ理由: 公式 Microphone 例と同じ排他なので、切替と `playRaw` が使えるかが分かる。音量は同梱ライブラリのマスタ音量である

検算

- タッチ → 録音再生 → 声が返る＝目的の前半
- 255 で書き込んだあと、会話に使える大きさで返る＝目的の後半
- 切替が生きる＝録って話す前提が埋まる

状態

- 声は返った
- 128 では小さかった
- 255 を書き込み済み
- 255 で大きさも OK

実践方法

- 使うファイルは [`firmware/clock_ws/src/speaker_self_test.cpp`](../firmware/clock_ws/src/speaker_self_test.cpp) の `playRec`
- データの送り方: 鳴らす音はマイクで録った自分の声。PC から音声ファイルは送らない
- 音量を変えるときだけ、かかとUSBで自己試験のファーム全体を書き込む

```
# StackChanで、マイクとスピーカーの切替と playRaw を見るために、画面を1回タッチして2秒話す
画面を1回タッチする。液晶が speak now になったら2秒話す。2回目は触らない。
```

```
# PCで、firmware/clock_ws に移り、録音再生の音量を上げた自己試験を本体に書く
cd firmware/clock_ws
```

```
# PCで、音量 255 の自己試験をビルドし、成功したらかかとUSBへアップロードする
../../.venv/bin/pio run -e speaker-self-test -t upload --upload-port /dev/ttyACM0
```

```
# StackChanで、音量 255 の録音再生を耳で確認するために、画面を1回タッチして2秒話す
画面を1回タッチする。液晶が speak now になったら2秒話す。2回目は触らない。
```

結果

- 声は返ったが、かなり小さかった
- 音量 255 の自己試験を書き込んだ
- 書き込み後、声は大きくなった。OK

結果詳細

```
声は返った。音はかなり小さい。
```

```
Hard resetting via RTS pin...
========================= [SUCCESS] Took 11.85 seconds =========================
```

全文: [`agent_reports/speaker_wav_rebuild_artifacts/step2_volume_upload.txt`](speaker_wav_rebuild_artifacts/step2_volume_upload.txt)

```
音が大きくなった。OK。
```

### Step 3 — 文をファームに入れて鳴らす

背景

- 会話の返答は、PC が文から音声を作り、本体へ送って鳴らす
- いま USB で音声を送ると、「作る」「送る」「鳴らす」が同時に疑われる
- 本体の再生だけを切るには、同じ文の音声をこの Step で作り、自己試験に入れ、本体へ書き、タッチで鳴らす
- USB で音声バイトを流すのは Step 5 である
- 会話ホスト [`host/server.py`](../host/server.py) はこの Step では動かさない

目的

- 「こんにちは。音声テストです。」が、本体スピーカーから日本語として聞こえること
- その音声は、この Step で PC が文から作ってファームに入れたものであること

手段

- PC が [`tools/make_known_speech.py`](../tools/make_known_speech.py) で、文を音声ファイルにする
- 音声ファイルは [`agent_reports/speaker_wav_rebuild_artifacts/hello.wav`](speaker_wav_rebuild_artifacts/hello.wav)
- 文から音声を作る実体は [`host/tts.py`](../host/tts.py)
- PC が [`tools/embed_wav.py`](../tools/embed_wav.py) で、そのファイルを [`firmware/clock_ws/include/test_speech_wav.h`](../firmware/clock_ws/include/test_speech_wav.h) にする
- PC が自己試験をビルドし、かかとUSBへ書く
- 書き込み後、本体はリセットされ、起動 tone が鳴る
- 利用者は画面を1回タッチして2秒話す（自己試験の録音。書き込みで最初からになる）
- もう1回タッチする
- 本体が [`firmware/clock_ws/src/speaker_self_test.cpp`](../firmware/clock_ws/src/speaker_self_test.cpp) の `playKnownWav` で、いま入れた音声を鳴らす
- この操作を選ぶ理由: USB で音声を送らずに、文→ファーム→再生 が一本で切れる

検算

- 文を音声にし、ファームへ入れ、書いて、タッチで日本語が聞こえる＝目的
- 再生が足りる＝USB 配送を外した欠けが埋まる

状態

- 音声ファイルを作った
- ヘッダにした
- 本体へ書いた
- 書き込み後の耳は聞こえた（「こんにちは。音声テストです。」）

実践方法

- 使うファイル
  - 文から音声にする: [`tools/make_known_speech.py`](../tools/make_known_speech.py)
  - 音声をファームの配列にする: [`tools/embed_wav.py`](../tools/embed_wav.py)
  - 鳴らす処理: [`firmware/clock_ws/src/speaker_self_test.cpp`](../firmware/clock_ws/src/speaker_self_test.cpp) の `playKnownWav`
- 送りの前（PC の中だけ。本体へは届かない）
  - [`make_known_speech.py`](../tools/make_known_speech.py) が文を [`hello.wav`](speaker_wav_rebuild_artifacts/hello.wav) にする
  - [`embed_wav.py`](../tools/embed_wav.py) が同じバイトを [`test_speech_wav.h`](../firmware/clock_ws/include/test_speech_wav.h) の配列にする
  - `pio run` のビルドが、その配列を自己試験の `firmware.bin` に含める
- データの送り方
  - 口: かかとUSB。デバイスは `/dev/ttyACM0`
  - 運ぶもの: 自己試験のバイナリ全体（`.pio/build/speaker-self-test/firmware.bin`）。WAV 単体のファイルではない。WAV のバイトは、この bin の中の配列である
  - 運ぶ操作: PlatformIO の `upload`。中で esptool がフラッシュを消し、bin を書く
  - 着く場所: 本体のフラッシュ（プログラムを覚えておくメモリ）。書き込みのあと本体はリセットされる
  - 着いたあとの動き: 起動 tone のあと、タッチ2回目で `playKnownWav` がフラッシュ上の配列を `playWav` に渡す
  - Step 5 との違い: Step 5 は起動したまま WAV をシリアルで流す。Step 3 は書き込みのときに bin ごと載せる
- 打ったコマンド

```
# PCで、試験用の一文を音声ファイルにするために、TTS の Python を実行する（USBは開かない）
.venv/bin/python tools/make_known_speech.py
```

```
# PCで、その音声を自己試験が読める配列にするために、埋め込みの Python を実行する
.venv/bin/python tools/embed_wav.py agent_reports/speaker_wav_rebuild_artifacts/hello.wav
```

```
# PCで、firmware/clock_ws に移る
cd firmware/clock_ws
```

```
# PCで、その音声入りの自己試験をビルドし、成功したらかかとUSBへアップロードする
../../.venv/bin/pio run -e speaker-self-test -t upload --upload-port /dev/ttyACM0
```

```
# StackChanで、書き込み後の自己試験を最初から進めるために、画面を1回タッチして2秒話す
画面を1回タッチする。液晶が speak now になったら2秒話す。
```

```
# StackChanで、いま入れた文の音声を鳴らすために、画面をもう1回タッチする
画面を1回タッチする。
```

結果

- [`hello.wav`](speaker_wav_rebuild_artifacts/hello.wav) を書いた
- [`test_speech_wav.h`](../firmware/clock_ws/include/test_speech_wav.h) にした
- かかとUSBへ書き込み、本体がリセットされた
- 「こんにちは。音声テストです。」が聞こえた

結果詳細

```
wrote agent_reports/speaker_wav_rebuild_artifacts/hello.wav
text=こんにちは。音声テストです。
bytes=124460 duration_s=3.89
```

全文: [`agent_reports/speaker_wav_rebuild_artifacts/step3_make_wav.txt`](speaker_wav_rebuild_artifacts/step3_make_wav.txt)

```
wrote firmware/clock_ws/include/test_speech_wav.h wav_bytes=124460 source_lines=10379
```

全文: [`agent_reports/speaker_wav_rebuild_artifacts/step3_embed.txt`](speaker_wav_rebuild_artifacts/step3_embed.txt)

```
Hard resetting via RTS pin...
========================= [SUCCESS] Took 11.77 seconds =========================
```

全文: [`agent_reports/speaker_wav_rebuild_artifacts/step3_upload.txt`](speaker_wav_rebuild_artifacts/step3_upload.txt)

```
聞こえた。
```

### Step 4 — PC で標準WAVを作る

背景

- Step 3 で、文から音声を作りファームへ入れて鳴らすところまでやる
- USB で音声を送るのはまだしない
- 送る前に、PC 上のファイルだけを見る必要がある

目的

- PC 上に、本体へ送るのと同じ文の音声ファイルがあること

手段

- PC だけで、Step 3 で書いた [`hello.wav`](speaker_wav_rebuild_artifacts/hello.wav) を確認する
- 本体は触らない
- この操作を選ぶ理由: 送る前に、ファイル単体が足りているかが分かる

検算

- PC 上に確認済みの音声ファイルがある＝目的
- 作る欠けが埋まる

状態

- 確認済み
- 本体は触っていない

実践方法

- 使うファイルは [`tools/inspect_known_speech.py`](../tools/inspect_known_speech.py)
- 対象は [`hello.wav`](speaker_wav_rebuild_artifacts/hello.wav)
- データの送り方: 送らない。PC 上のファイルを読むだけ

```
# PCで、送る前に試験用 WAV が本体の playWav が読める形か確認する（USBは開かない）
.venv/bin/python tools/inspect_known_speech.py
```

結果

- ファイルは本体が読める形だった
- 無音でもクリップでもない
- 本体は触っていない

結果詳細

```
path=agent_reports/speaker_wav_rebuild_artifacts/hello.wav
bytes=124460 crc32=bb518a81
codec_name=pcm_s16le
sample_rate=16000
channels=1
bits_per_sample=16
duration_s=3.888
peak=20865
rms=1797
ok
```

全文: [`agent_reports/speaker_wav_rebuild_artifacts/step4_inspect.txt`](speaker_wav_rebuild_artifacts/step4_inspect.txt)

### Step 5 — USB で WAV を送る

背景

- Step 3 までで再生と形式が切れていれば、残りは PC から本体へのバイト配送である
- かかとUSB は CDC シリアルである

目的

- PC が送った WAV が欠けず届くこと
- Step 3 と同じ日本語が本体から聞こえること
- 音が始まるまでの待ちが、会話に使える短さであること

手段

- PC の [`tools/send_known_speech.py`](../tools/send_known_speech.py) が音声ファイルを本体へ送る
- 本体は全部揃ってから `playWav` で鳴らす
- 処理の本体側は [`firmware/clock_ws/src/speaker_self_test.cpp`](../firmware/clock_ws/src/speaker_self_test.cpp)
- 1回目は合図が細かすぎて、音が始まるまで約 20 秒かかった
- 合図の間隔を広げ、本体へ自己試験を書き直してから同じファイルを再送した
- さらに、開いたあとの固定待ちをやめ、起動 tone の JSON を見てから送るようにした
- この操作を選ぶ理由: 配送と再生を分けて確認できる。往復の回数が待ちの本体である

検算

- 送った音声が Step 3 と同じ日本語で聞こえる＝目的
- 待ちが短くなる＝配送の欠けの残りが埋まる

状態

- 1回目: 届いて聞こえた。送信に約 20 秒かかった
- 合図の間隔を広げて書き込み、再送した
- 3回目: コマンド全体 8.32 秒。日本語として聞こえた。待ちも足りる

実践方法

- 使うファイル
  - 送り手: [`tools/send_known_speech.py`](../tools/send_known_speech.py)
  - 送りの中身: [`host/speaker_test.py`](../host/speaker_test.py) の `send_wav`
  - 受け手: [`firmware/clock_ws/src/speaker_self_test.cpp`](../firmware/clock_ws/src/speaker_self_test.cpp)
  - 送るファイル: [`hello.wav`](speaker_wav_rebuild_artifacts/hello.wav)
- データの送り方
  - 口: かかとUSB。デバイスは `/dev/ttyACM0`
  - 運ぶもの: [`hello.wav`](speaker_wav_rebuild_artifacts/hello.wav) のバイト全体。ファームの bin ではない
  - 運ぶ操作: 先に `SPEAK_BEGIN`（長さと検査和）を JSON で送る。本体が `SPEAK_READY` してから WAV のバイトを送る。本体が `SPEAK_PROGRESS` を返してから次の塊を送る。全部揃い検査和が一致してから `playWav`。1回目は合図が細かく約 20 秒かかったので、間隔を広げて本体を書き直し、同じコマンドで再送した
  - 着く場所: 本体の受信バッファ。一致したあとスピーカー
  - Step 3 との違い: Step 3 は `pio ... -t upload` で bin ごとフラッシュに載せる。Step 5 は起動中に WAV をシリアルで流す
- 打ったコマンド

```
# PCで、Step 3 と同じ WAV をかかとUSBで本体へ送り、playWav させる
.venv/bin/python tools/send_known_speech.py --wav agent_reports/speaker_wav_rebuild_artifacts/hello.wav --port /dev/ttyACM0
```

```
# PCで、firmware/clock_ws に移り、合図の間隔を広げた自己試験を本体に書く
cd firmware/clock_ws
```

```
# PCで、その自己試験をビルドし、成功したらかかとUSBへアップロードする
../../.venv/bin/pio run -e speaker-self-test -t upload --upload-port /dev/ttyACM0
```

```
# PCで、同じ WAV を再送し、待ちが短くなったかを見る
.venv/bin/python tools/send_known_speech.py --wav agent_reports/speaker_wav_rebuild_artifacts/hello.wav --port /dev/ttyACM0
```

```
# PCで、起動 tone の JSON を待ってから送る版を、同じ WAV で再送する
.venv/bin/python tools/send_known_speech.py --wav agent_reports/speaker_wav_rebuild_artifacts/hello.wav --port /dev/ttyACM0
```

結果

- 1回目: 届いて「こんにちは。音声テストです。」が聞こえた。送信に約 20 秒かかった
- 合図の間隔を広げて書き込んだ
- 2回目: 長さと検査和は一致。コマンド全体は 10.23 秒（開いて待つ 2.5 秒と再生約 4 秒を含む）
- 3回目: 起動 tone の JSON を待ってから送り、合図もさらに粗くした。コマンド全体は 8.32 秒。日本語として聞こえた。待ちも足りる

結果詳細

```
serial opened /dev/ttyACM0
send wav bytes=124460 crc32=bb518a81 duration=3.89s peak=20865
{'type': 'SPEAK_READY', 'id': 1}
{'type': 'SPEAK_PROGRESS', 'id': 1, 'got': 1024}
...
{'type': 'SPEAK_RECEIVED', 'id': 1, 'bytes': 124460, 'crc32': 3142683265}
{'type': 'SPEAK_FINISHED', 'id': 1, 'played_ms': 3888}
finished {'type': 'SPEAK_FINISHED', 'id': 1, 'played_ms': 3888}
```

全文: [`agent_reports/speaker_wav_rebuild_artifacts/step5_send.txt`](speaker_wav_rebuild_artifacts/step5_send.txt)

```
Hard resetting via RTS pin...
========================= [SUCCESS] Took 11.82 seconds =========================
```

全文: [`agent_reports/speaker_wav_rebuild_artifacts/step5_faster_upload.txt`](speaker_wav_rebuild_artifacts/step5_faster_upload.txt)

```
{'type': 'SPEAK_READY', 'id': 1}
{'type': 'SPEAK_PROGRESS', 'id': 1, 'got': 8192}
...
{'type': 'SPEAK_RECEIVED', 'id': 1, 'bytes': 124460, 'crc32': 3142683265}
{'type': 'SPEAK_FINISHED', 'id': 1, 'played_ms': 3888}
elapsed_sec=10.23
```

全文: [`agent_reports/speaker_wav_rebuild_artifacts/step5_send_faster.txt`](speaker_wav_rebuild_artifacts/step5_send_faster.txt)

```
{'type': 'SELF_TEST', 'phase': 'tone', 'playWav': True, 'played_ms': 400}
{'type': 'SPEAK_READY', 'id': 1}
{'type': 'SPEAK_PROGRESS', 'id': 1, 'got': 16384}
...
{'type': 'SPEAK_FINISHED', 'id': 1, 'played_ms': 3888}
elapsed_sec=8.32
```

全文: [`agent_reports/speaker_wav_rebuild_artifacts/step5_send_faster2.txt`](speaker_wav_rebuild_artifacts/step5_send_faster2.txt)

### Step 6 — 会話へ戻す

背景

- 会話はマイク → PC の文字起こしと LLM → スピーカーである
- スピーカー単体が Step 5 までできたあとに、認識と LLM を足す
- 現状、本体は自己試験のままである

目的

- 固定文 TTS、LLM 返答、マイク 3 往復が、本体スピーカーで聞こえること

手段

- かかとUSB で会話用プログラム（`m5stack-cores3`）を書く
- `host/server.py` の再生を Step 5 と同じ WAV プロトコルにする
- 失敗した段で止める
- この操作を選ぶ理由: 再生経路が確定したあとに、会話の入出力を同じスピーカーへ戻せる

検算

- 会話プログラム + 同じ再生 → 3 往復が聞こえる＝目的
- 会話出力の欠けが埋まる

状態

- 未実施
