from speakproto import (
    json_in_audio_frame,
    on_crc_mismatch,
    on_ready_timeout,
    parse_device_line,
    should_send_binary,
    speak_begin_line,
)
from wavutil import crc32


def test_begin_line_contains_fields():
    line = speak_begin_line(7, 100, 1)
    assert line.endswith("\n")
    assert '"SPEAK_BEGIN"' in line
    assert '"id":7' in line
    assert '"bytes":100' in line


def test_parse_ready():
    msg = parse_device_line('{"type":"SPEAK_READY","id":7}')
    assert msg["type"] == "SPEAK_READY"
    assert msg["id"] == 7


def test_no_binary_before_ready():
    assert should_send_binary(False) is False
    assert should_send_binary(True) is True


def test_crc_used_in_begin():
    payload = b"abc"
    line = speak_begin_line(1, len(payload), crc32(payload))
    assert str(crc32(payload)) in line


def test_chunk_waits_for_progress():
    from speakproto import next_chunk_after_progress

    assert next_chunk_after_progress(1024, 500, 5000) is None
    assert next_chunk_after_progress(1024, 1024, 5000) == 1024
    assert next_chunk_after_progress(4096, 4096, 5000) == 904
    assert next_chunk_after_progress(5000, 5000, 5000) is None


def test_ready_timeout_does_not_send_binary():
    assert on_ready_timeout() == "abort_no_binary"
    assert should_send_binary(False) is False
    assert on_crc_mismatch() == "no_play"
    clock = b'{"type":"clock","line0":"2026/09/09"}\n'
    assert json_in_audio_frame(clock) is True
    assert json_in_audio_frame(b"RIFF") is False
