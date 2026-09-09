from asr import pcm_mean_abs


def test_silence_is_quiet():
    assert pcm_mean_abs(b"\x00\x00" * 100) == 0


def test_loud_sample():
    assert pcm_mean_abs((10000).to_bytes(2, "little", signed=True) * 4) == 10000
