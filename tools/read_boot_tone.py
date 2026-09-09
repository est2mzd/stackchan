#!/usr/bin/env python3
"""起動toneのシリアルログを取る。

背景:
    会話の出力の末端は本体スピーカーと AW88298（スピーカー用アンプ）。
    そこが死んでいれば、このあとの WAV も USB も無意味である。
    自己試験プログラムは起動時に M5.Speaker.tone(880, 400) を呼ぶ。
    かかとUSB（本体かかと側 USB-C）の CDC シリアルを開くと、
    ESP32-S3 は rst:0x15 で再起動する。抜き差しと同じリセット経路である。

目的:
    リセット直後の boot / tone JSON をファイルに残すこと。
    プログラムが tone を 400 ms 実行したことはログで分かる。
    スピーカーからビープが聞こえたかは、このプログラムでは判定しない。

手段:
    このファイルを python3 で実行する。WAV は送らない。
    シリアルを開き、起動ログを読み、artifact に書く。
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import serial


def main() -> None:
    parser = argparse.ArgumentParser(
        description="かかとUSBを開いて起動toneのJSONを保存する"
    )
    # CoreS3 の USB Serial/JTAG は、この環境では /dev/ttyACM0 に出る。
    parser.add_argument("--port", default="/dev/ttyACM0")
    # 長いログはレポート本文に置かず、artifact に残す。
    parser.add_argument(
        "-o",
        "--output",
        default="agent_reports/speaker_wav_rebuild_artifacts/step1_tone.txt",
    )
    args = parser.parse_args()
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    # pyserial の既定は DTR/RTS を立てて開く。
    # 立てたまま開くとリセットの仕方が変わり、ログの頭が欠けることがある。
    # False にしても、開くこと自体で USB_UART_CHIP_RESET は起きる。
    ser = serial.Serial()
    ser.port = args.port
    ser.baudrate = 115200
    ser.timeout = 0.2
    ser.dtr = False
    ser.rts = False
    ser.open()

    # 再起動から M5.begin と tone(880, 400) が終わるまで待つ。
    # 400 ms の tone のあと SELF_TEST の JSON が出る。
    time.sleep(2.5)

    # 起動ログと JSON をまとめて読む。WAV も SPEAK_* も送らない。
    buf = b""
    end = time.time() + 5.0
    while time.time() < end:
        buf += ser.read(4096)
    ser.close()

    text = buf.decode("utf-8", errors="replace")
    out.write_text(text)
    print(text)


if __name__ == "__main__":
    main()
