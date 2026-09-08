from datetime import datetime

from clock_format import clock_message, format_clock_lines


def test_format_clock_lines_english():
    now = datetime(2026, 9, 8, 22, 58, 33)
    assert format_clock_lines(now, "en") == ["2026/09/08", "22:58:33", "Tuesday"]


def test_format_clock_lines_japanese():
    now = datetime(2026, 9, 8, 22, 58, 33)
    assert format_clock_lines(now, "ja") == ["2026/09/08", "22:58:33", "火曜日"]


def test_clock_message_type():
    msg = clock_message(datetime(2026, 1, 1, 0, 0, 0), "en")
    assert msg["type"] == "clock"
    assert len(msg["lines"]) == 3
