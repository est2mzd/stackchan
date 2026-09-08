# フェーズ3 実施報告

実施日: 2026-09-09  
入力: `agent_reports/001_plan.md`、`004_phase2.md`  
作業ディレクトリ: `/home/takuya/work/stackchan`

---

## 背景

フェーズ2でマイク PCM とモード語句はホストに載せた。次は会話：文字起こし → LLM → TTS → スピーカー。画面に発話と応答を出す。LLM は本体では動かさない。

---

## 目的

1. マイク → ASR → LLM → TTS → スピーカー
2. 画面にユーザ発話と応答
3. LLM を echo / Ollama / ChatGPT で切替
4. 会話中の「時計モード」で時計に戻る

---

## 結論

パイプラインは `host/server.py` に入れた。LLM の echo は「こんにちは」→「「こんにちは」ですね。」を確認した。Ollama と ChatGPT はキー/サーバが無いので未確認。TTS は edge-tts。実機スピーカの `SPEAK_DONE` は再フラッシュ直後の試験ではシリアル空で未確認。再生バッファは `speak_end` でまとめて `playRaw` する。

```
+---------------------------+        USB         +---------------------------+
| PC                        | <----------------> | StackChan                 |
|                           |  ユーザの声 PCM    |                           |
|  中でやること             |  返事の音声 PCM    |  中でやること             |
|    文字にする             |  画面の2行         |    マイク（再生中は止める）|
|    LLM で返事を作る       |                    |    スピーカーで鳴らす     |
|    音声にする             |                    |    液晶に発話と返事       |
+---------------------------+                    +---------------------------+
```

起動例:

```
.venv/bin/python host/server.py --serial /dev/ttyACM0 --llm echo --asr whisper --tts edge
```

ChatGPT は `OPENAI_API_KEY` と `--llm openai`。Ollama は `--llm ollama --llm-base-url http://127.0.0.1:11434`。

---

## 詳細

コマンド： .venv/bin/python -c 'from llm import complete; import asyncio; print(asyncio.run(complete("こんにちは","echo","","","")))'

- 目的： キー無しでも会話の形（echo）が返るか見る

引数：
- `backend="echo"` — 入力を短く返すだけの頭脳
- `"こんにちは"` — 試験用の発話

結果：
```
「こんにちは」ですね。
```

コマンド： .venv/bin/python - <<'PY' （440Hz PCM を speak_start/pcm/speak_end で送る）

- 目的： 本体スピーカがホスト PCM を再生し SPEAK_DONE を返すか見る

引数：
- `{"type":"speak_start"}` — マイク停止、再生準備
- `{"type":"pcm","data":...}` — 16kHz 16bit
- `{"type":"speak_end"}` — 再生して SPEAK_DONE

結果：
```
SPEAK_DONE False n 0
```

フラッシュ直後にポートを開いた試験で、起動ログも含め受信 0 バイトだった。再生経路は未確認。時計とマイク試験（フェーズ2）では同じポートで受信できている。

コマンド： （未実行）Ollama または ChatGPT に実発話を渡す

- 目的： 計画の LLM 切替を実サーバで見る

引数： なし

結果：
```
（未実行）この PC に ollama も OPENAI_API_KEY も無い。
```
