#!/usr/bin/env python3
"""試験用の一文を、PC上の音声ファイルにする。

背景:
    会話の返答は、いずれ PC が文から音声を作り、USB で本体へ送る。
    いま USB で送ると、「文から作る」「送る」「鳴らす」が同時に疑われる。
    本体の再生だけを切るには、同じ文の音声をファームに入れてから鳴らす。
    その最初の材料が、このファイルが書く WAV である。

目的:
    「こんにちは。音声テストです。」の音声ファイルが PC 上にあること。
    このプログラムはシリアルを開かない。本体へは送らない。

手段:
    host/tts.py の synth_edge_wav を呼ぶ。
    できたバイトを artifact の WAV に書く。
    次のプログラム tools/embed_wav.py が、この WAV をファームの配列にする。
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# host/tts.py を import するために、リポジトリの host をパスへ入れる。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "host"))
from tts import synth_edge_wav
from wavutil import inspect_wav


def main() -> None:
    parser = argparse.ArgumentParser(
        description="試験用の一文を WAV ファイルにする。USB は開かない。"
    )
    parser.add_argument("--text", default="こんにちは。音声テストです。")
    parser.add_argument(
        "-o",
        "--output",
        default="agent_reports/speaker_wav_rebuild_artifacts/hello.wav",
    )
    args = parser.parse_args()
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    # 会話ホスト host/server.py は使わない。文から音声だけを作る。
    wav = asyncio.run(synth_edge_wav(args.text))
    out.write_bytes(wav)
    info = inspect_wav(wav)
    print(f"wrote {out}")
    print(f"text={args.text}")
    print(f"bytes={len(wav)} duration_s={info['duration_s']:.2f}")


if __name__ == "__main__":
    main()
