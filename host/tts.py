from __future__ import annotations

import asyncio
import io
import wave


def wav_to_pcm16_mono(wav_bytes: bytes, sample_rate: int = 16000) -> bytes:
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        nch = wf.getnchannels()
        sw = wf.getsampwidth()
        rate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
    if sw != 2:
        raise ValueError("need 16-bit wav")
    if nch == 2:
        import array

        samples = array.array("h")
        samples.frombytes(frames)
        mono = array.array("h", (samples[i] for i in range(0, len(samples), 2)))
        frames = mono.tobytes()
    if rate != sample_rate:
        import audioop

        frames, _state = audioop.ratecv(frames, 2, 1, rate, sample_rate, None)
    return frames


async def synth_edge(text: str, voice: str = "ja-JP-NanamiNeural") -> bytes:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice)
    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    mp3 = buf.getvalue()
    return await asyncio.to_thread(_mp3_to_pcm, mp3)


def _mp3_to_pcm(mp3: bytes) -> bytes:
    import subprocess
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "in.mp3"
        dst = Path(td) / "out.wav"
        src.write_bytes(mp3)
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(src), "-ac", "1", "-ar", "16000", "-f", "wav", str(dst)],
            check=True,
            capture_output=True,
        )
        return wav_to_pcm16_mono(dst.read_bytes(), 16000)


async def synth_none(text: str) -> bytes:
    return b""
