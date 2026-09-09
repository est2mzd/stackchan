#!/usr/bin/env python3
"""WAV を、自己試験ファームが読める C の配列にする。

背景:
    本体の playWav は、実行中のプログラムの中にあるバイト列を読む。
    USB で今送るのではなく、書き込み時にフラッシュへ載せる。
    PC 上の WAV のままでは、C++ のソースにならない。

目的:
    firmware/clock_ws/include/test_speech_wav.h が、渡した WAV と同じバイトを
    配列として持つこと。

手段:
    WAV を読み、inspect で本体が読める形かを見る。
    ヘッダファイルへ配列と長さを書く。
    このプログラムだけでは本体は鳴らない。
    次に PlatformIO で自己試験をビルドし、かかとUSBへ書く。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "host"))
from wavutil import inspect_wav, wav_to_c_header


def main() -> None:
    parser = argparse.ArgumentParser(
        description="WAV を自己試験用の C ヘッダにする。USB は開かない。"
    )
    parser.add_argument("wav")
    parser.add_argument(
        "-o",
        "--output",
        default="firmware/clock_ws/include/test_speech_wav.h",
    )
    args = parser.parse_args()
    wav = Path(args.wav).read_bytes()
    # 壊れた WAV をファームに入れない。
    inspect_wav(wav)
    header = (
        "#pragma once\n"
        "#include <stdint.h>\n"
        "#include <stddef.h>\n\n"
        + wav_to_c_header(wav, "test_speech_wav")
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(header)
    print(f"wrote {out} wav_bytes={len(wav)} source_lines={header.count(chr(10))}")


if __name__ == "__main__":
    main()
