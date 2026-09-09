# 今までの不具合とコード

## 背景

StackChan（SKU K151 / CoreS3）を PC 頭脳で動かす途中で、同じ系統の不具合が何度も出た。ユーザ指示は `user_directions/001_objective.md`（マイク→PC の LLM→本体スピーカーと画面、時計、Calendar）。スマホアプリは使わない。接続はかかと側 USB（`/dev/ttyACM0`）。

個別の実施記録は `agent_reports/007_pytest_ros.md` から `021_static.md` まで。この文書はそれらをコード付きで一枚にまとめる。執筆時点のソースは `firmware/clock_ws/src/main.cpp` と `host/server.py` など。

## 目的

| 完了条件 | 状態 |
| --- | --- |
| 出た不具合を時系列で列挙する | 完了 |
| 当時／いまのコードを添える | 完了 |
| 直ったものと未完了を分ける | 完了。スピーカーの「ざーーー」は未完了 |

## 結論

会話の流れ（マイク→文字→ChatGPT→音声）はホスト側では通ることがある。液晶の文字と `SPEAK_DONE` は出る。ただし **本体スピーカーは言語にならず、ざーーーというノイズのまま** である。これがいまの最優先の未完了である。

```
+---------------------------+        USB         +---------------------------+
| PC                        | -----------------> | StackChan                 |
|                           |  時計 JSON         |                           |
|  中でやること             |  speak_start + PCM |  中でやること             |
|    Whisper で文字にする   |                    |    液晶に文字            |
|    ChatGPT で返事         |                    |    スピーカーで再生      |
|    edge-tts → 16kHz PCM   | <----------------- |    ※いまはざーーー     |
|                           |  touch / PCM       |    マイクは録れる        |
|                           |  SPEAK_DONE        |                           |
+---------------------------+                    +---------------------------+
```

使わなかった構成（PC のスピーカーで鳴らす）:

```
+---------------------------+                    +---------------------------+
| PC                        |                    | StackChan                 |
|                           |                    |                           |
|  中でやること             |     （使わない）   |  中でやること             |
|    PC 本体で TTS 再生     |                    |    画面だけ               |
+---------------------------+                    +---------------------------+
```

不具合一覧（新しいものが下）。

| # | ユーザが言ったこと | 原因（コード） | いま |
| --- | --- | --- | --- |
| 1 | pytest が即死 | ROS Jazzy の pytest プラグイン | `pytest.ini` で回避。直った |
| 2 | 「未接続」 | ホスト停止、または会話 UI でも 2.5 秒タイムアウト | 時計画面だけタイムアウト。直った |
| 3 | 8000 番が使えない | `clock_server.py` / `server.py` が 8000 | 既定 `15151`。直った |
| 4 | ChatGPT に繋がらない | OpenAI の URL が Ollama の `:11434` になる | `openai_base()` で公式 URL。直った |
| 5 | echo なのに返事が復唱 | README が `--llm echo` | `--llm openai`。運用の話 |
| 6 | 「考え中」で止まる | シリアル同時書き、Whisper が読取りを止める | ロックと別タスク。直った |
| 7 | 文字が切れる | 1 行中央寄せ | 12 字×4 行左寄せ。直った |
| 8 | 2 回目が止まる | 再生中に `loop` が `delay`、listen を捨てる | 非同期再生。一部直った |
| 9 | ASR が空文字 | `vad_filter=True`、振幅 400 で捨てる | VAD なし、閾値 80。一部直った |
| 10 | 勝手に ChatGPT が喋る | USB が TTS JSON で詰まり、Whisper が幻聴 | 生 PCM に変更。直った |
| 11 | 音が本体から出ない | TTS を USB で止めていた／PC 再生は拒否 | 本体へ生 PCM。経路は生きた |
| 12 | 反応なし | 時計のまま話す、タッチ取りこぼし、録音が終わらない | 押し検出、最大 4 秒。一部直った |
| 13 | フリーズ | マイク PCM を JSON で連打、`Serial.println` で loop 停止 | 録音はメモリに溜めて一括。直った |
| 14 | 2 回目フリーズ＋無音 | 148 KB を内部 RAM に溜め、`delay(5)` で受信遅れ | チャンク再生→その後 PSRAM 一括 |
| 15 | ザザッ／ざーーー | 再生中バッファ上書き、16 bit ずれ、**いまもノイズ** | **未完了** |

いま残っているスピーカー経路（ノイズの正本）:

ホストは 16 kHz リトルエンディアンの 16 bit モノラル PCM を送り、本体は PSRAM に貯めて `playRaw(..., 16000, stereo=false)` する。装置側の I2S は 48 kHz。CoreS3 のマイクとスピーカーは同じ I2S ポートを共有する。この組み合わせが「ざーーー」の最有力である。

## 詳細

コマンド： sed -n '211,250p' firmware/clock_ws/src/main.cpp

- 目的： いまの再生コード（ノイズの出どころ）をそのまま出す

引数：
- `-n '211,250p'` — 行 211–250
- `firmware/clock_ws/src/main.cpp` — 本体ファーム

結果：
```
static void startSpeaker()
{
  stopMicHardware();
  speaking = true;
  play_active = false;
  pcm_expect = 0;
  pcm_got = 0;
  auto spk = M5.Speaker.config();
  spk.sample_rate = kSpkHwRate;
  spk.stereo = false;
  spk.task_priority = 5;
  M5.Speaker.config(spk);
  if (!speaker_up)
  {
    M5.Speaker.begin();
    speaker_up = true;
  }
  M5.Speaker.setVolume(180);
  delay(50);
}

static void stopSpeaker()
{
  if (spk_store == nullptr || pcm_got < 4)
  {
    finishPlay();
    return;
  }
  const size_t n = pcm_got / 2;
  const int16_t *samples = reinterpret_cast<const int16_t *>(spk_store);
  M5.Speaker.stop();
  const bool ok = M5.Speaker.playRaw(samples, n, kSampleRate, false, 1, -1, true);
  if (!ok)
  {
    finishPlay();
    return;
  }
  play_active = true;
  play_from_ms = millis();
}
```

意味: `kSpkHwRate` は 48000、`kSampleRate` は 16000。`playRaw` の第 4 引数 `false` はモノラル、第 5 引数 `1` は 1 回再生。M5Unified は再生中にこのポインタを読み続ける（コピーしない）。PSRAM 上の `spk_store` を再生終了まで壊してはいけない。

コマンド： sed -n '106,140p' host/server.py

- 目的： PC が返事の PCM を USB にどう書くかを出す

引数：
- `-n '106,140p'` — `speak()`
- `host/server.py` — 統合ホスト

結果：
```
header = (json.dumps({"type": "speak_start", "bytes": len(pcm)}) + "\n").encode("utf-8")
...
await asyncio.sleep(0.08)
...
piece = pcm[off : off + 4096]
self._write_raw(piece, flush=False)
```

意味: 先に JSON 1 行、80 ms 空けてから生バイト。本体は改行までを JSON、そのあと `bytes` 個を PCM として読む。ずれると 16 bit の組が壊れ、ざーーーになる。

コマンド： sed -n '30,56p' host/tts.py

- 目的： 返事の音声データが何フォーマットかを出す

引数：
- `-n '30,56p'`
- `host/tts.py`

結果：
```
communicate = edge_tts.Communicate(text, voice)  # ja-JP-NanamiNeural
...
ffmpeg ... -ac 1 -ar 16000 -f wav
return wav_to_pcm16_mono(dst.read_bytes(), 16000)
```

意味: MP3 を 16 kHz・1 ch・16 bit WAV にして PCM だけ送る。ホストが作っているデータ自体は言語の波形である。ノイズは主に本体側の再生解釈である。

コマンド： sed -n '33,48p' host/asr.py

- 目的： 空文字 ASR を直したあとの閾値を出す

引数：
- `-n '33,48p'`
- `host/asr.py`

結果：
```
if len(pcm) < 8000:
    return ""
if pcm_mean_abs(pcm) < 80:
    return ""
...
self.model.transcribe(..., language="ja", condition_on_previous_text=False)
```

意味: 以前は `vad_filter=True` と振幅 400 で日本語を捨てていた（`014`）。いま VAD は無い。静かな 4 秒録音はまだ `asr ''` になり、聞けが続く。

以下、過去の不具合とコードの対応。

### 1. pytest が ROS で落ちる（007）

`/opt/ros/jazzy` の `launch_testing_ros_pytest_entrypoint` が未知フックを登録する。対策は `pytest.ini` の `addopts = -p no:launch_testing_ros_pytest_entrypoint` と `tools/pytest_noload.pth`。

### 2. 「未接続」（008）

本体は最後のホスト時刻から 2.5 秒で赤文字にする。当時は会話画面でも同じ判定だった。いまは時計画面だけ。

```
if (ui == UI_CLOCK && (millis() - last_host_ms) > kDisconnectAfterMs)
{
  drawDisconnected();  // 「未接続」
}
```

ホストを止めると時計は「未接続」になる。これは仕様。

### 3. ポート 8000（009, 010）

当時 `WS_PORT = 8000`。他プロセスと衝突した。いま:

```
WS_PORT = 15151
```

ファームの `SERVER_PORT_H` も 15151。USB だけなら WebSocket は使っていない。

### 4. OpenAI が Ollama ポートに行く（012）

`--llm openai` なのに `11434` が残ると ChatGPT に届かない。

```
def openai_base(base_url: str) -> str:
    url = (base_url or "").strip()
    if not url or "11434" in url:
        return OPENAI_DEFAULT  # https://api.openai.com/v1
```

### 5. echo と ChatGPT（README）

`--llm echo` は「〜ですね。」と返すだけ。会話は:

```
.venv/bin/python host/server.py --serial /dev/ttyACM0 --weekday en --asr whisper --tts edge --llm openai
```

### 6. 「考え中」フリーズ（011）

3 点が重なった。

1. 時計 JSON と会話 JSON を同時に USB へ書く
2. Whisper 中にシリアルを読まない
3. echo なのに「考え中」を出して、壊れた行が残る

いまは `self.io` ロック、`asyncio.to_thread` で Whisper、echo では考え中を出さない。

```
def thinking_placeholder(backend: str) -> bool:
    return backend != "echo"
```

### 7. 文字切れ（013）

長い日本語を中央 1 行に載せた。いま `host/chatfmt.py`:

```
def chat_screen(user: str, reply: str) -> list[str]:
    return [clip_line(user, 12), *wrap_lines(reply, 12, 3)]
```

画面はゴシック 16 pt・左寄せ。LLM は「日本語で 2 文まで、1 文 20 字以内」。

### 8. 2 回目が止まる（015）

再生を `delay` で待つと `loop` が止まり、その間の `listen` を捨てた。いま再生は `playRaw` の非同期。`listen` は再生中なら `want_listen` に積む。

ホストは `SPEAK_DONE` まで次の聞けを送らない。来なければ `SPEAK_DONE timeout` のあと `idle`。

### 9. ASR 空文字と幻聴（014, 016）

当時:

- マイク PCM を `{"type":"pcm","data":"<base64>"}` で毎 32 ms 送信
- Whisper `vad_filter=True`
- 振幅 400 未満を捨てる
- USB が詰まると `CLOCK_TIMEOUT`、無音を認識して「キャンディング」などの幻聴 → ChatGPT が勝手に返事

いまマイクは本体メモリに溜め、録音後に生 PCM 一括。Whisper の VAD は切った。

### 10. 音が出ない（017）

一時、USB 詰まり回避のためホストが `tts skip usb` していた。ユーザは PC スピーカー再生を拒否。いま `synth_edge` → `speak_start` + 生 PCM。PC では再生しない。

### 11. 反応なし（018）

時計のまま話してもマイクは開かない。タッチは `wasClicked()` だと取りこぼす。いまは押している間に 1 回 `{"type":"touch"}`。会話中のタッチでは時計に戻らない。「時計モード」で戻る。

録音は声のあと 0.6 秒の静けさ、または最大 4 秒。

### 12. フリーズ（019）

録音中に Base64 JSON を毎ループ `Serial.println` すると USB が埋まり、描画もタッチも止まる。いま `sendPcmToHost()` は録音終了後だけ。録音中は「聞いています」と残り秒。

### 13. 無音の 2 回目（020）

148224 バイト（約 4.6 秒）を `std::vector` で内部 RAM に `assign` し、全部揃ってから `playRaw`。`loop` 末尾の `delay(5)` のあいだ USB が 64 バイトずつしか進まず、ホストの 8 秒待ちが先に切れた。そのあと送る `idle` / `listen` が PCM 待ちに食われ、2 回目が壊れた。

対策として一度は 3 面バッファで受信しながら再生した。M5Unified の注意（再生中ポインタを上書きするな）を守れておらず、ザザッになった。

### 14. ざーーー（021 と本報告。未完了）

3 面バッファをやめて PSRAM 一括 + `playRaw` 1 回にした。ホストログ例（2026-09-09 22:29 以降）:

```
asr '1話は'
reply 'どの作品の1話ですか？詳しく教えてください。'
tts device bytes=168960
SPEAK_DONE
```

ホストは波形を送り、本体は再生完了を返している。ユーザには言語ではなく「ざーーー」。候補は次。

1. `playRaw` が PSRAM を直接読む／キャッシュと DMA の食い違い
2. I2S 装置 48 kHz とデータ 16 kHz の変換失敗
3. CoreS3 でマイク `end` 直後のスピーカー `begin` が AW88298 を正しく起こしていない
4. `playRaw(..., stereo=false)` なのに I2S が 16 bit×2 スロットで、片側ノイズになる
5. `Serial.readBytes` 中に他 JSON が混ざって PCM が壊れる（可能性は低い。`SPEAK_DONE` は長さどおり終わっている）

CoreS3 / StackChan のピン（M5Unified）: マイクもスピーカーも `I2S_NUM_1`、BCK=GPIO34、WS=GPIO33。データだけ IN=GPIO14、OUT=GPIO13。同時には使えない。`startSpeaker` の `delay(50)` はその切替用。

コマンド： （ログ確認）ホスト 225254 相当

- 目的： 「ざーーー」のときホストが PCM を送り SPEAK_DONE を受けたか確認する

引数： なし

結果：
```
tts device bytes=168960
SPEAK_DONE
pcm_start bytes=39936
...
pcm binary timeout
```

`pcm binary timeout` は、2 回目以降のマイク一括受信が 3 秒以内に終わらなかったときにホストが出す。ノイズ本体とは別件だが、USB の食い違いは残っている。

未完了の次の手（この文書では実施しない）: 内部 RAM の小さな正弦波を `playRaw` してスピーカー単体を確認する。通れば USB の PCM 解釈、通らなければ I2S / AW88298。16 kHz のまま装置も 16 kHz にする、またはステレオ複製して送る、を切り分ける。
