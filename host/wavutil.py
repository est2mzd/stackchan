from __future__ import annotations

import subprocess
import wave
import zlib
from io import BytesIO
from pathlib import Path


class WavError(ValueError):
    pass


def crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def inspect_wav(data: bytes) -> dict:
    if len(data) < 44:
        raise WavError("WAV too short")
    if data[0:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise WavError("not RIFF/WAVE")
    if data[8:16] != b"WAVEfmt ":
        raise WavError("WAVE/fmt not contiguous; M5Unified playWav would reject")
    with wave.open(BytesIO(data), "rb") as wf:
        nch = wf.getnchannels()
        sw = wf.getsampwidth()
        rate = wf.getframerate()
        nframes = wf.getnframes()
        frames = wf.readframes(nframes)
    if sw != 2:
        raise WavError(f"need 16-bit, got {sw * 8}-bit")
    if nch != 1:
        raise WavError(f"need mono, got {nch} ch")
    if rate != 16000:
        raise WavError(f"need 16000 Hz, got {rate}")
    if len(frames) != nframes * 2:
        raise WavError("data length mismatch")
    if nframes < 1600:
        raise WavError("WAV shorter than 0.1 s")
    peak = 0
    total = 0
    for i in range(0, len(frames), 2):
        s = int.from_bytes(frames[i : i + 2], "little", signed=True)
        a = abs(s)
        if a > peak:
            peak = a
        total += a
    rms = total // nframes if nframes else 0
    if peak < 100:
        raise WavError("near silence")
    if peak >= 32767:
        raise WavError("clipped")
    return {
        "channels": nch,
        "sample_rate": rate,
        "bits": 16,
        "nframes": nframes,
        "data_bytes": len(frames),
        "duration_s": nframes / rate,
        "peak": peak,
        "rms": rms,
    }


def canonicalize_pcm16_mono_16k(data: bytes) -> bytes:
    info = inspect_wav(data)
    with wave.open(BytesIO(data), "rb") as wf:
        frames = wf.readframes(wf.getnframes())
    buf = BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(frames)
    out = buf.getvalue()
    if out[8:16] != b"WAVEfmt ":
        raise WavError("canonicalize failed WAVE/fmt layout")
    inspect_wav(out)
    if info["nframes"] != inspect_wav(out)["nframes"]:
        raise WavError("canonicalize lost frames")
    return out


def mp3_to_wav16_mono(mp3: bytes) -> bytes:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "in.mp3"
        dst = Path(td) / "out.wav"
        src.write_bytes(mp3)
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(src),
                "-acodec",
                "pcm_s16le",
                "-ar",
                "16000",
                "-ac",
                "1",
                str(dst),
            ],
            check=True,
            capture_output=True,
        )
        wav = dst.read_bytes()
    return canonicalize_pcm16_mono_16k(wav)


def ffprobe_wav(path: Path) -> str:
    r = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_name,sample_rate,channels,bits_per_sample",
            "-of",
            "default=noprint_wrappers=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return r.stdout


def wav_to_c_header(wav: bytes, symbol: str) -> str:
    lines = [
        f"static const uint8_t {symbol}[] = {{",
    ]
    for i in range(0, len(wav), 12):
        chunk = wav[i : i + 12]
        body = ", ".join(f"0x{b:02x}" for b in chunk)
        lines.append(f"  {body},")
    lines.append("};")
    lines.append(f"static const size_t {symbol}_len = {len(wav)};")
    lines.append("")
    return "\n".join(lines)


def known_crc_vector() -> tuple[bytes, int]:
    return b"123456789", 0xCBF43926
