#!/usr/bin/env python3
"""起動中の本体へ、試験用 WAV をかかとUSBで送る。

背景:
    Step 3 は自己試験の bin ごとフラッシュに載せた。
    Step 5 は、すでに動いている自己試験へ、同じ文の WAV をシリアルで流す。
    会話ホスト host/server.py は使わない。

目的:
    PC が送ったバイトが欠けず届くこと。
    Step 3 と同じ「こんにちは。音声テストです。」が本体から聞こえること。
    このプログラムの JSON だけでは耳の合格にしない。

手段:
    かかとUSBのシリアルを開く（開くと本体はリセットされる）。
    起動 tone の JSON を待ってから送る。固定秒数では待たない。
    SPEAK_BEGIN（長さと検査和）を JSON で送る。
    本体の SPEAK_READY のあと、WAV のバイトを送る。
    本体が SPEAK_PROGRESS を返してから次の塊を送る。
    合図の間隔は本体の kProgEvery と同じ。
    全部揃い検査和が一致してから、本体が playWav する。
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "host"))
from speaker_test import send_wav, wait_until_tone_done
from wavutil import inspect_wav

try:
    import serial as serial_mod
except ImportError:
    serial_mod = None


async def amain() -> None:
    parser = argparse.ArgumentParser(
        description="hello.wav をかかとUSBで本体へ送る。"
    )
    parser.add_argument("--port", default="/dev/ttyACM0")
    parser.add_argument(
        "--wav",
        default="agent_reports/speaker_wav_rebuild_artifacts/hello.wav",
    )
    args = parser.parse_args()
    if serial_mod is None:
        raise SystemExit("pyserial is required")

    path = Path(args.wav)
    wav = path.read_bytes()
    inspect_wav(wav)

    # 開くと ESP32-S3 は rst:0x15 で再起動する。tone が終わるまで待つ。
    ser = serial_mod.Serial()
    ser.port = args.port
    ser.baudrate = 115200
    ser.timeout = 0.2
    ser.dtr = False
    ser.rts = False
    ser.open()
    print(f"serial opened {args.port}", flush=True)
    await wait_until_tone_done(ser)
    finished = await send_wav(ser, wav, sid=1)
    print(f"finished {finished}", flush=True)
    ser.close()


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
