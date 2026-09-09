# Agent指示書：StackChan K151で「文字を日本語音声として本体スピーカーから再生」する経路の再構築

## 1. 目的

StackChan（SKU K151 / CoreS3）で、PCが生成した任意の日本語音声を、PCのスピーカーではなくStackChan本体のスピーカーから明瞭に再生できる状態にする。

今回はASR、LLM、時計、画面、サーボを同時に直さない。まず次の一本だけを成立させる。

```text
PC上の固定日本語テキスト
  → TTSで標準WAVを生成
  → USB CDCでWAV全体を転送
  → CoreS3でWAVを検証
  → M5Unifiedの標準APIで再生
  → 「こんにちは。音声テストです。」と聞こえる
```

その後に、既存の `Whisper → ChatGPT → TTS` 経路へ戻す。

## 2. 最重要の訂正

`agent_reports/023_hiss.md` にある次の断定を、確定原因として扱わないこと。

> AW88298はステレオI2Sを期待するため、`spk.stereo = false` が「ざーーー」の原因だった。

これは現時点では仮説であり、ユーザによる「日本語として聞こえた」という実機確認がない。CoreS3がAW88298の16-bit I2Sアンプを搭載することは公式資料で確認できるが、「必ずステレオ設定が必要」「モノラル設定だからホワイトノイズになる」という因果は、確認した公式資料からは立証できない。

今後は、独自の `sample_rate`、`stereo`、I2S設定を増やして原因を推測しない。まずM5UnifiedがCoreS3用に選ぶデフォルト設定と公式サンプルの再生手順に戻す。

## 3. 調査で確認できた事実

1. CoreS3はAW88298の16-bit I2Sアンプ、1Wスピーカー、ES7210＋デュアルマイクを搭載する。
   - https://docs.m5stack.com/en/core/CoreS3

2. M5UnifiedはCoreS3とM5StackChanを正式な対応機種として列挙し、`Speaker`、`Microphone`、WAV再生、MP3ストリームの公式例を提供している。
   - https://github.com/m5stack/M5Unified
   - https://docs.m5stack.com/en/arduino/m5unified/speaker_class

3. M5Unified公式のMicrophone例は、CoreS3を含む対象でマイクとスピーカーを同時使用せず、再生前に `M5.Mic.end()`、`M5.Speaker.begin()`、再生後に `M5.Speaker.end()`、`M5.Mic.begin()` と切り替える。また、録音した16 kHz・16-bit・monoデータを `playRaw(..., 16000, false, ...)` で再生している。
   - https://github.com/m5stack/M5Unified/blob/master/examples/Basic/Microphone/Microphone.ino

4. M5Unified公式のSD WAV例は `M5.begin()` の後に独自I2S設定を行わず、WAVヘッダからsample rate、bit depth、channel数を読み、複数バッファを順番に `playRaw` へ渡している。
   - https://github.com/m5stack/M5Unified/blob/master/examples/Advanced/Speaker_SD_wav_file/Speaker_SD_wav_file.ino

5. M5Unified公式AquesTalk例は、8 kHz・16-bit・monoの合成音声を3面バッファで `playRaw` へ連続投入している。したがって、入力音声がmonoや8/16 kHzであることだけをノイズ原因とは断定できない。
   - https://github.com/m5stack/M5Unified/blob/master/examples/Advanced/Speak_with_AquesTalk/Speak_with_AquesTalk.ino

6. Stack-chanコミュニティの実装資料は、任意文の読み上げ方法として「外部TTSサーバへ問い合わせ、生成音声をストリームする」方式を明記し、VoiceVoxなどの利用実績を挙げている。
   - https://github.com/rt-net/stack-chan/blob/main/firmware/docs/text-to-speech.md

7. M5UnifiedにはHTTP上のMP3を取得・デコードし、M5スピーカーへ流す公式WebRadio例もある。将来Wi-Fiストリーミングへ移行する場合の根拠になるが、今回は既存要件どおり、まずUSB CDCで完成させる。
   - https://github.com/m5stack/M5Unified/blob/master/examples/Advanced/WebRadio_with_ESP8266Audio/WebRadio_with_ESP8266Audio.ino

## 4. 採用方針

最初の完成形は、USB CDCを使った「WAV一括転送後再生」とする。

- PC側TTS: 既存の `edge-tts` を継続使用してよい。
- 転送形式: 生PCMではなく、ヘッダを含む標準RIFF/WAVEファイル全体。
- WAV形式: PCM signed 16-bit little-endian、1 channel、16,000 Hz。
- 本体側再生: `M5.Speaker.playWav(wav_bytes, wav_size)` を第一候補とする。
- I2S設定: `M5.begin()` が選ぶCoreS3既定値を使い、`spk.sample_rate` と `spk.stereo` を手動上書きしない。
- マイク/スピーカー: 公式Microphone例と同じく明示的に排他切替する。
- バッファ: WAVデータはPSRAMへ保持し、`M5.Speaker.isPlaying()` がfalseになるまで解放・上書きしない。

この方式を選ぶ理由は、WAVヘッダにsample rate、channel、bit depth、data長が含まれ、ホストと本体で音声フォーマットの解釈がずれにくいからである。また、数秒の短い返答なら16 kHz・16-bit・monoで毎秒約32 KBであり、CoreS3の8 MB PSRAMに十分収まる。

## 5. 禁止事項

- いきなり会話全体を起動して耳だけで原因を推測しない。
- `SPEAK_DONE` が出たことを「音声再生成功」と報告しない。これは処理完了ログにすぎない。
- `delay(80)` のような時間待ちを、JSONとバイナリの境界保証として使わない。
- 受信データ長とCRCが一致する前に再生しない。
- 再生中のPSRAMまたはリングバッファを上書きしない。
- M5Unifiedの動作確認前にAW88298を直接初期化しない。
- `023_hiss.md` の結論をコピーして「修正済み」としない。
- ASR無音、Whisper幻聴、LLM、画面レイアウトを今回のブランチで同時修正しない。

## 6. 実装手順

### Step 0：現状保存とブランチ

1. `git status`、現在ブランチ、HEADを記録する。
2. ユーザの未コミット変更を消さない。
3. 作業ブランチを `feature/speaker-wav-rebuild` とする。すでに同名がある場合は勝手に削除せず、状態を確認して適切な派生名を使う。
4. 現在の `firmware/clock_ws/src/main.cpp`、`host/server.py`、`host/tts.py` と依存バージョンを調べる。
5. M5Unifiedの実際の固定バージョンと、その版の `playWav` / `playRaw` シグネチャをローカルの依存ソースから確認する。ネット上のmasterだけを前提にしない。

### Step 1：スピーカー単体の最小試験

既存アプリへ統合する前に、CoreS3用の最小ファームまたはコンパイル時フラグ `SPEAKER_SELF_TEST` を作る。

試験順序は固定する。

1. `M5.begin()` と `M5.Speaker.setVolume(...)` だけで短いtoneを鳴らす。
2. M5Unified公式Microphone例をほぼそのまま移植し、2秒録音→録音内容再生を行う。
3. 「こんにちは。音声テストです。」という既知の日本語WAVをファーム資産として再生する。

Step 1では独自の `spk.sample_rate` / `spk.stereo` 設定を入れない。マイクとスピーカーの切替は次の形を基準にする。

```cpp
while (M5.Mic.isRecording()) {
  M5.delay(1);
}
M5.Mic.end();
M5.Speaker.begin();
M5.Speaker.setVolume(128);  // 最初は大音量にしない

const bool accepted = M5.Speaker.playWav(wav_data, wav_size);
while (accepted && M5.Speaker.isPlaying()) {
  M5.update();
  M5.delay(1);
}

M5.Speaker.end();
M5.Mic.begin();
```

ローカルのM5Unified版で引数が異なる場合は、その版のヘッダに合わせる。コンパイルを通すためだけの推測引数は使わない。

判定:

| 結果 | 判断 |
| --- | --- |
| toneも鳴らない | 電源、音量、ボード判定、M5Unified初期化の層を調べる |
| toneは鳴るが録音再生がノイズ | Mic/Speaker切替または公式例との差分を調べる |
| 録音再生は聞こえるが既知WAVだけノイズ | WAV生成・ヘッダ・bit depth・channel・バッファ寿命を調べる |
| 既知WAVが日本語として聞こえる | スピーカー/I2S/再生APIは合格。USB転送へ進む |

ここでユーザに実機確認を依頼し、「日本語として聞こえた／聞こえない」を記録する。聞こえていないのにStep 2以降を成功扱いしない。

### Step 2：PC側で標準WAVを固定生成

会話処理を通さない専用コマンドを用意する。

例:

```bash
.venv/bin/python -m host.speaker_test \
  --serial /dev/ttyACM0 \
  --text 'こんにちは。音声テストです。'
```

`edge-tts` の出力をffmpegで必ず次の形式へ正規化する。

```bash
ffmpeg -y -i input.mp3 -acodec pcm_s16le -ar 16000 -ac 1 output.wav
ffprobe -v error -show_entries stream=codec_name,sample_rate,channels,bits_per_sample \
  -of default=noprint_wrappers=1 output.wav
```

期待値:

```text
codec_name=pcm_s16le
sample_rate=16000
channels=1
bits_per_sample=16
```

さらにPythonテストでRIFF/WAVE、`fmt `、`data` チャンク、data長、duration、最大振幅、RMSを確認する。無音、クリップ、空ファイルを送信前に拒否する。

同じ `output.wav` をUbuntu側でも一度再生し、日本語として正しいことを確認できる手順を表示する。ただし完成条件はStackChan本体からの再生であり、PC再生への設計変更はしない。

### Step 3：USB CDC転送を明示的なプロトコルにする

現在の「JSON 1行→80 ms待つ→裸のPCM」という方式を廃止する。最低限、次の状態遷移を実装する。

```text
Host: SPEAK_BEGIN(id, codec=wav, bytes=N, crc32=C)
Device: SPEAK_READY(id)
Host: Nバイトを送る
Device: 長さとCRC32を検証
Device: SPEAK_RECEIVED(id, bytes=N, crc32=C)
Device: マイク停止→WAV再生
Device: SPEAK_FINISHED(id, played_ms=...)
Device: スピーカー停止→マイク再開
```

要件:

- `id` を全応答に含め、過去の応答と混ざらないようにする。
- `SPEAK_READY` を受けるまでバイナリを送らない。固定sleepに依存しない。
- 本体はNバイト受信中、JSONパーサへバイナリを渡さない。
- 受信タイムアウト時はバッファを破棄し、テキストモードへ明示的に復帰する。
- CRC不一致時は再生せず `SPEAK_ERROR(id, reason=crc)` を返す。
- WAVサイズ上限を決める。PSRAM空き量を確認し、安全に確保できないサイズは受信開始前に拒否する。
- 再生中も時計描画などが必要なら、長いblocking delayではなく小さいループまたはタスクで処理する。
- 最初は全WAV受信後再生に限定する。リアルタイム分割再生は、明瞭な再生が3回連続で成功した後の別Stepにする。

### Step 4：受信したWAVをそのまま再生

1. 受信先はPSRAMとし、確保成功を確認する。
2. RIFF/WAVEヘッダを本体でも検証する。
3. `M5.Mic.end()` の前に録音完了を待つ。
4. `M5.Speaker.begin()` 後、`M5.Speaker.playWav(...)` を呼ぶ。
5. `playWav` の戻り値をログへ出す。
6. `isPlaying()` がfalseになるまでWAVバッファを保持する。
7. 終了後にバッファを解放し、`M5.Speaker.end()` → `M5.Mic.begin()` とする。

もしローカル版の `playWav` が対象WAVを受け付けない場合だけ、公式 `Speaker_SD_wav_file` 例と同じWAVパーサ＋3面バッファの `playRaw` へ切り替える。その場合もWAVヘッダの値を使い、`16000` やmonoを本体側で二重に決め打ちしない。

### Step 5：固定文から会話経路へ戻す

次を順番に試す。

1. 同一の既知WAVをUSBで3回連続再生。
2. `speaker_test --text` で異なる短文を3種類再生。
3. LLMを通さず、固定文字列→TTS→本体再生。
4. LLM返答→TTS→本体再生。
5. マイク→Whisper→LLM→TTS→本体再生を3会話連続。

前段で失敗したら後段へ進まず、その境界のログと成果物を残す。

## 7. 必須テスト

### ホスト自動テスト

- WAVがPCM s16le / 16 kHz / mono / 16-bitである。
- WAVのdataサイズと実データ長が一致する。
- CRC32計算が既知ベクトルで一致する。
- `SPEAK_READY` 前にバイナリ送信しない。
- READYタイムアウト、受信タイムアウト、CRC不一致を正しく扱う。
- 同時に時計送信が走っても、音声フレームへJSONが混入しない。

### ファーム単体テストまたは検証ログ

- Nバイトちょうどでバイナリ受信状態を抜ける。
- 1バイト不足、1バイト超過、CRC不一致で再生しない。
- `playWav` がfalseなら成功ログを出さない。
- 再生終了前にバッファを解放しない。
- エラー後に通常JSONコマンドを再び受信できる。

### 実機合格条件

- 本体スピーカーから「こんにちは。音声テストです。」と明瞭に聞こえる。
- 同じ固定文を3回連続で再生して、3回ともノイズだけにならない。
- その後、異なる日本語3文がそれぞれ区別して聞き取れる。
- 3回の会話を行い、2回目以降もフリーズしない。
- 再生後にマイクが復帰する。

ユーザの聴感確認が必要な項目は、勝手に「合格」と記録しない。

## 8. ログと報告書

次の新規報告を作る。

```text
agent_reports/024_speaker_wav_rebuild.md
```

報告書には以下を含める。

1. 変更前の事実
2. 参考にした公式URL
3. `023_hiss.md` のどの断定を仮説へ戻したか
4. 変更ファイルと変更理由
5. 実行した全コマンドと主要出力
6. `ffprobe` の結果
7. 送信byte数、受信byte数、CRC32
8. `playWav` の戻り値と再生時間
9. 自動テスト結果
10. 実機の各試験結果
11. ユーザ確認待ちの項目
12. 未解決事項と次に切り分ける層

`022_bug_catalog.md` と `023_hiss.md` は履歴として残し、過去の記述を消さない。最終的に実機で日本語を確認できた後だけ、`023_hiss.md` に「追試結果」として事実を追記する。

## 9. Agentの最終回答形式

最終回答は、単に「修正しました」と書かず、次の形式にする。

```text
結論：日本語音声が本体から聞こえた／まだ聞こえていない／ユーザ確認待ち

合格した最終段階：Step X
失敗した最初の段階：Step Y（失敗時のみ）
原因として確定したこと：...
まだ仮説のこと：...
変更ファイル：...
テスト結果：...
ユーザが次に行う操作：コマンド1本＋本体操作
報告書：agent_reports/024_speaker_wav_rebuild.md
```

ユーザが行う操作は、可能な限り「Agentがホストを起動済み→画面を1回タッチ→聞こえた内容を答える」だけにする。
