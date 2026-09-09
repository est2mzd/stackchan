#!/usr/bin/env python3
"""PC 上の試験用 WAV を、送る前に確認する。

背景:
    Step 3 で文から音声ファイルを作り、ファームに入れて鳴らした。
    次は同じファイルを USB で送る。
    送る前に、PC 上のファイル単体が足りているかを見る。
    本体を使うと、ファイルの問題と配送の問題が混ざる。

目的:
    hello.wav が、本体の playWav が読む形であること。
    無音やクリップでないこと。

手段:
    host/wavutil.py の inspect_wav と ffprobe_wav を使う。
    シリアルは開かない。本体へは送らない。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "host"))
from wavutil import crc32, ffprobe_wav, inspect_wav


def main() -> None:
    parser = argparse.ArgumentParser(
        description="試験用 WAV を確認する。USB は開かない。"
    )
    parser.add_argument(
        "wav",
        nargs="?",
        default="agent_reports/speaker_wav_rebuild_artifacts/hello.wav",
    )
    args = parser.parse_args()
    path = Path(args.wav)
    wav = path.read_bytes()
    info = inspect_wav(wav)
    print(f"path={path}")
    print(f"bytes={len(wav)} crc32={crc32(wav):08x}")
    print(ffprobe_wav(path).rstrip())
    for key in (
        "channels",
        "sample_rate",
        "bits",
        "duration_s",
        "peak",
        "rms",
    ):
        print(f"{key}={info[key]}")
    print("ok")


if __name__ == "__main__":
    main()
