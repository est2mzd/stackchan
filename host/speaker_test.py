#!/usr/bin/env python3
"""USB で WAV を送る本体側試験の送り手。

背景:
    会話ホストは時計・認識・LLM も抱える。配送だけを切るには専用の送り手が要る。
目的:
    SPEAK_BEGIN のあと WAV バイトを送り、本体の受信ログを読むこと。
手段:
    tools/send_known_speech.py から send_wav を呼ぶ。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from speakproto import speak_begin_line
from tts import synth_edge_wav
from wavutil import crc32, ffprobe_wav, inspect_wav, canonicalize_pcm16_mono_16k

try:
    import serial as serial_mod
except ImportError:
    serial_mod = None


def pc_play_hint(path: Path) -> str:
    return (
        f"PCで内容確認する場合（完成条件ではない）: ffplay -autoexit {path}  "
        f"または aplay {path}"
    )


async def read_json_line(ser, timeout: float) -> dict:
    deadline = time.monotonic() + timeout
    buf = b""
    while time.monotonic() < deadline:
        chunk = ser.read(256)
        if chunk:
            buf += chunk
            if b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                text = line.decode("utf-8", errors="replace").strip()
                if not text:
                    continue
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    print(f"device {text[:160]}", flush=True)
                    continue
        else:
            await asyncio.sleep(0.02)
    raise TimeoutError("timeout waiting for device JSON")


async def wait_until_tone_done(ser, timeout: float = 4.0) -> None:
    """シリアルオープンでリセットされたあと、起動 tone の JSON を待つ。

    固定の 2.5 秒待ちより短い。tone の JSON は再生が終わってから出る。
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        remain = deadline - time.monotonic()
        if remain <= 0:
            break
        try:
            msg = await read_json_line(ser, min(0.4, remain))
        except TimeoutError:
            continue
        print(msg, flush=True)
        if msg.get("type") == "SELF_TEST" and msg.get("phase") == "tone":
            return
    print("tone wait timeout; sending anyway", flush=True)


async def send_wav(ser, wav: bytes, sid: int) -> dict:
    info = inspect_wav(wav)
    csum = crc32(wav)
    print(
        f"send wav bytes={len(wav)} crc32={csum:08x} duration={info['duration_s']:.2f}s peak={info['peak']}",
        flush=True,
    )
    header = speak_begin_line(sid, len(wav), csum)
    ser.write(header.encode("utf-8"))
    ser.flush()
    ready = False
    while not ready:
        msg = await read_json_line(ser, 8.0)
        print(msg, flush=True)
        if msg.get("type") == "SPEAK_READY" and int(msg.get("id", -1)) == sid:
            ready = True
        if msg.get("type") == "SPEAK_ERROR" and int(msg.get("id", -1)) == sid:
            raise RuntimeError(msg)
    off = 0
    # 本体 firmware kProgEvery と同じ。
    chunk = 16384
    while off < len(wav):
        n = min(chunk, len(wav) - off)
        ser.write(wav[off : off + n])
        ser.flush()
        off += n
        if off >= len(wav):
            break
        got_ok = False
        while not got_ok:
            msg = await read_json_line(ser, 5.0)
            print(msg, flush=True)
            if msg.get("type") == "SPEAK_ERROR" and int(msg.get("id", -1)) == sid:
                raise RuntimeError(msg)
            if msg.get("type") == "SPEAK_PROGRESS" and int(msg.get("id", -1)) == sid:
                if int(msg.get("got", 0)) >= off:
                    got_ok = True
    received = False
    finished = None
    while finished is None:
        msg = await read_json_line(ser, 25.0)
        print(msg, flush=True)
        typ = msg.get("type")
        if int(msg.get("id", -1)) != sid:
            continue
        if typ == "SPEAK_ERROR":
            raise RuntimeError(msg)
        if typ == "SPEAK_RECEIVED":
            received = True
            if int(msg.get("bytes", -1)) != len(wav) or int(msg.get("crc32", -1)) != csum:
                raise RuntimeError(f"device mismatch {msg}")
        if typ == "SPEAK_FINISHED":
            finished = msg
        if typ == "SELF_TEST" and msg.get("accepted") is True:
            finished = {
                "type": "SPEAK_FINISHED",
                "id": sid,
                "played_ms": msg.get("played_ms"),
            }
    if not received:
        raise RuntimeError("SPEAK_FINISHED without SPEAK_RECEIVED")
    return finished


async def amain() -> None:
    parser = argparse.ArgumentParser(description="Send one test WAV to StackChan over USB")
    parser.add_argument("--serial", default="/dev/ttyACM0")
    parser.add_argument("--text", default="こんにちは。音声テストです。")
    parser.add_argument("--wav", default="", help="use an existing WAV instead of TTS")
    parser.add_argument("--out", default="agent_reports/speaker_wav_rebuild_artifacts/hello.wav")
    parser.add_argument(
        "--generate-only",
        action="store_true",
        help="write WAV and run ffprobe; do not open USB",
    )
    args = parser.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.wav:
        wav = canonicalize_pcm16_mono_16k(Path(args.wav).read_bytes())
    else:
        wav = await synth_edge_wav(args.text)
    out.write_bytes(wav)
    print(ffprobe_wav(out), flush=True)
    print(inspect_wav(wav), flush=True)
    print(pc_play_hint(out), flush=True)
    if args.generate_only:
        print(f"wrote {out} bytes={len(wav)} crc32={crc32(wav):08x}", flush=True)
        return
    if serial_mod is None:
        raise SystemExit("pyserial is required")

    ser = serial_mod.Serial()
    ser.port = args.serial
    ser.baudrate = 115200
    ser.timeout = 0.2
    ser.dtr = False
    ser.rts = False
    ser.open()
    print(f"serial opened {args.serial}", flush=True)
    await wait_until_tone_done(ser)
    finished = await send_wav(ser, wav, sid=1)
    print(f"finished {finished}", flush=True)
    ser.close()


def main() -> None:
    asyncio.run(amain())


if __name__ == "__main__":
    main()
