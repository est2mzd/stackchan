from __future__ import annotations

import json


def speak_begin_line(sid: int, nbytes: int, crc: int) -> str:
    return json.dumps(
        {
            "type": "SPEAK_BEGIN",
            "id": sid,
            "codec": "wav",
            "bytes": nbytes,
            "crc32": crc,
        },
        separators=(",", ":"),
    ) + "\n"


def parse_device_line(line: str) -> dict:
    line = line.strip()
    if not line:
        raise ValueError("empty")
    msg = json.loads(line)
    if "type" not in msg:
        raise ValueError("no type")
    return msg


def should_send_binary(got_ready: bool) -> bool:
    return got_ready


def on_ready_timeout() -> str:
    return "abort_no_binary"


def on_crc_mismatch() -> str:
    return "no_play"


def json_in_audio_frame(frame: bytes) -> bool:
    stripped = frame.lstrip()
    return stripped.startswith(b"{") or stripped.startswith(b"[")


def next_chunk_after_progress(sent: int, got: int, total: int, chunk: int = 1024) -> int | None:
    if got < sent:
        return None
    if sent >= total:
        return None
    return min(chunk, total - sent)
