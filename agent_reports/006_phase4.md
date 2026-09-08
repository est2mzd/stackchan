# フェーズ4 実施報告

実施日: 2026-09-09  
入力: `agent_reports/001_plan.md`、`005_phase3.md`  
作業ディレクトリ: `/home/takuya/work/stackchan`

---

## 背景

時計画面の上に、Google Calendar の予定を X 分前に出して読み上げる。トークンは本体に置かない。過ぎた予定は初期設定では捨てる。

---

## 目的

1. ホストが Calendar API（OAuth）で予定を取る
2. X 分前（初期 10）に通知する
3. 時計を残したままタイトルを足す
4. TTS で読む
5. 電源オフ中に過ぎた予定は捨てる（初期）

---

## 結論

通知の時刻判定と読み上げ文は単体テストで確認した。OAuth 用の `host/google_credentials.json` が無いので、実 Google 予定の取得は未実行。デモは `--calendar-demo-in-sec` でローカル予定を差し込める。トークンパスは gitignore。

```
+---------------------------+                    +---------------------------+
| PC                        |                    | StackChan                 |
|                           |                    |                           |
|  中でやること             |  --- USB JSON ---> |  中でやること             |
|    Calendar を見る        |  日付・時刻・曜日  |    時計画面のまま         |
|    X分前なら文言を作る    |  + 予定タイトル    |    4行目に予定            |
|    音声でも読む           |  読み上げ PCM      |    スピーカー             |
+---------------------------+                    +---------------------------+
         ^
         | OAuth（未実施。credentials が無い）
         |
+---------------------------+
| Google Calendar           |
+---------------------------+
```

---

## 詳細

コマンド： .venv/bin/pytest -q host/test_calendar_notify.py

- 目的： X 分前に一度だけ通知し、過ぎた予定は捨てるか見る

引数：
- `-q` — 短い結果
- `host/test_calendar_notify.py` —  convene 判定と「10分後、定例ミーティングです」

結果：
```
...                                                                      [100%]
```

（`host/test_clock_format.py host/test_intent.py host/test_calendar_notify.py` をまとめて走らせた全体は 9 passed。calendar は 3 件）

コマンド： ls host/google_credentials.json

- 目的： OAuth クライアント秘密があるか見る

引数：
- `host/google_credentials.json` — Google Cloud のデスクトップアプリ JSON。gitignore

結果：
```
ls: cannot access 'host/google_credentials.json': No such file or directory
```

コマンド： （未実行）InstalledAppFlow で primary カレンダーを読む

- 目的： 実アカウントの今後 24 時間の予定を取る

引数： なし

結果：
```
（未実行）credentials が無い。コードは host/calendar_google.py。
```

ホスト起動でデモ予定を使う例:

```
.venv/bin/python host/server.py --serial /dev/ttyACM0 --notify-minutes 1 --calendar-demo-in-sec 70 --calendar-demo-title 定例 --asr none --tts none --llm echo
```
