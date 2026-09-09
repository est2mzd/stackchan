from wavutil import crc32, inspect_wav, known_crc_vector, WavError, canonicalize_pcm16_mono_16k
import wave
from io import BytesIO


def _make_tone_wav(frames: int = 16000, amp: int = 4000) -> bytes:
    samples = bytearray()
    for i in range(frames):
        s = amp if (i // 20) % 2 == 0 else -amp
        samples += int(s).to_bytes(2, "little", signed=True)
    buf = BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(bytes(samples))
    return buf.getvalue()


def test_crc32_known_vector():
    data, expect = known_crc_vector()
    assert crc32(data) == expect


def test_inspect_ok_tone():
    info = inspect_wav(_make_tone_wav())
    assert info["sample_rate"] == 16000
    assert info["channels"] == 1
    assert info["bits"] == 16
    assert info["data_bytes"] == info["nframes"] * 2


def test_canonicalize_is_contiguous_fmt():
    raw = _make_tone_wav()
    out = canonicalize_pcm16_mono_16k(raw)
    assert out[8:16] == b"WAVEfmt "
    assert out[36:40] == b"data"


def test_inspect_rejects_silence():
    buf = BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 16000)
    try:
        inspect_wav(buf.getvalue())
        raise AssertionError("expected WavError")
    except WavError as exc:
        assert "silence" in str(exc)


def test_inspect_rejects_short():
    try:
        inspect_wav(b"RIFF")
        raise AssertionError("expected WavError")
    except WavError:
        pass


def test_inspect_rejects_wrong_rate():
    buf = BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(44100)
        wf.writeframes(b"\x00\x10" * 8000)
    try:
        inspect_wav(buf.getvalue())
        raise AssertionError("expected WavError")
    except WavError as exc:
        assert "16000" in str(exc)


def test_inspect_rejects_stereo():
    buf = BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x10\x00\x10" * 8000)
    try:
        inspect_wav(buf.getvalue())
        raise AssertionError("expected WavError")
    except WavError as exc:
        assert "mono" in str(exc)
