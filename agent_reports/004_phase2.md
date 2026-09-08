# フェーズ2 実施報告

実施日: 2026-09-09  
入力: `agent_reports/001_plan.md`、`003_phase1.md`  
作業ディレクトリ: `/home/takuya/work/stackchan`

---

## 背景

フェーズ1で USB 時計画面は通った。次はマイク音声を PC が受け、「時計モード」「会話モード」で画面を切り替える。タッチでも同じ切替をする。

---

## 目的

1. 本体マイクの PCM がホストに届く
2. ASR が「時計モード」なら時計、「会話モード」「戻って」なら会話画面
3. 再生中は録音しない
4. タッチでもモード切替できる

---

## 結論

PCM は USB シリアルの JSON（`type=pcm`）でホストに届くことを実機で確認した。意図判定は単体テスト 3 件成功。実機で人が「時計モード」と発話した ASR と、画面タッチは未確認（エージェントが触れない）。再生中は `speak_start` で Mic を止める。

ホストは `host/server.py`。ファームは `firmware/clock_ws/` を拡張した。

```
+---------------------------+        USB         +---------------------------+
| PC                        | <----------------> | StackChan                 |
|                           |  PCM JSON          |                           |
|  中でやること             |  時計 / 会話 JSON  |  中でやること             |
|    音声を文字にする       |  タッチ通知        |    マイクで録る           |
|    「時計モード」を見る   |                    |    液晶に時計か文字       |
|    時計なら日時を送る     |                    |    タッチしたら知らせる   |
+---------------------------+                    +---------------------------+
```

---

## 詳細

コマンド： export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1

- 目的： ROS の pytest プラグインを読まずにテストする

引数：
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` — 自動プラグインを止める

結果：
```
（環境変数を設定。stdout なし）
```

コマンド： .venv/bin/pytest -q host/test_clock_format.py host/test_intent.py host/test_calendar_notify.py

- 目的： 時計文字列と「時計モード」判定がホストで通るか見る

引数：
- `-q` — 短い結果
- `host/test_intent.py` — 時計/会話の語句

結果：
```
.........                                                                [100%]
9 passed in 0.02s
```

コマンド： .venv/bin/pio run -e m5stack-cores3 -t upload --upload-port /dev/ttyACM0

- 目的： マイク対応ファームを実機に書く

引数：
- `-e m5stack-cores3` — CoreS3 環境
- `-t upload` — 書き込み
- `--upload-port /dev/ttyACM0` — USB ポート

結果：
```
Hash of data verified.
Leaving...
Hard resetting via RTS pin...
========================= [SUCCESS] Took 16.38 seconds =========================
```

コマンド： .venv/bin/python - <<'PY' （listen を送り pcm_start / pcm / pcm_end を待つ）

- 目的： 本体マイクのフレームが PC に届くか見る

引数：
- `{"type":"listen"}` — 録音開始
- `{"type":"idle"}` — 録音停止
- 保存 `agent_reports/phase2_artifacts/serial_io.txt`

結果：
```
READY True
CLOCK_APPLIED True
pcm_start True
pcm_end True
pcm_json_lines 5
```

コマンド： （未実行）本体の前で「時計モード」と発話して ASR 文字列を取る

- 目的： 実機音声で意図判定まで通す

引数： なし

結果：
```
（未実行）エージェントがマイクに向かって話せない。語句判定は単体テストのみ。
```

コマンド： （未実行）画面をタッチして `{"type":"touch"}` を取る

- 目的： タッチで時計/会話が切替わるか見る

引数： なし

結果：
```
（未実行）ファームは wasClicked で touch を送る。実機操作は未確認。
```
