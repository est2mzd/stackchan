# 背景
- StackChanを、202608に購入したが、使い方がわからない
- スマホアプリと連携したいわけではないが、うまく連携できない
  - 参考: https://zenn.dev/shogaku/articles/stackchan-pairing-firmware?utm_source=chatgpt.com


# StackChanを使ってやりたいこと
1. StackChanと会話
  - 入力 = StackChanのマイク
  - 処理 = PC or Jetson に用意したLocal LLM or ChatGPT
  - 出力 = StackChanのスピーカー + 画面の文字
  - PCとの接続 = 無線 or 有線

2. StackChanを時計モードにする
  - 入力 = StackChanのマイク(時計モード　という音声で時計モードになる)
  - 処理 = PC or Jetson から文字列作成 or 内蔵EPS32で文字列作成
  - 出力 = StackChanのモニタ.例: 2026/09/08</br>22:58:33</br>Tuesday
  - PCとの接続 = 無線 or 有線

3. Google Calendarと同期して、X分前に予定を音とディスプレイで教える
  - 入力 = Google Calendar と連動した PCにあるアプリ
  - 処理 = PC or Jetson から文字列作成 or 内蔵EPS32で文字列作成
  - 出力 = StackChanのモニタ.例: 2026/09/08</br>22:58:33</br>Tuesday + 予定を音声で読み上げ
  - PCとの接続 = 無線 or 有線