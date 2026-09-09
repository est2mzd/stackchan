from __future__ import annotations

import io
import wave


def pcm16_to_wav(pcm: bytes, sample_rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def pcm_mean_abs(pcm: bytes) -> int:
    n = len(pcm) // 2
    if n == 0:
        return 0
    total = 0
    for i in range(0, n * 2, 2):
        total += abs(int.from_bytes(pcm[i : i + 2], "little", signed=True))
    return total // n


class WhisperAsr:
    def __init__(self, model_size: str = "base") -> None:
        from faster_whisper import WhisperModel

        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")

    def transcribe(self, pcm: bytes, sample_rate: int = 16000) -> str:
        if len(pcm) < 8000:
            return ""
        if pcm_mean_abs(pcm) < 80:
            return ""
        import tempfile

        wav = pcm16_to_wav(pcm, sample_rate)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
            tmp.write(wav)
            tmp.flush()
            segments, _info = self.model.transcribe(
                tmp.name,
                language="ja",
                condition_on_previous_text=False,
            )
            return "".join(seg.text for seg in segments).strip()


class NullAsr:
    def transcribe(self, pcm: bytes, sample_rate: int = 16000) -> str:
        return ""
