from chatfmt import chat_screen, clip_line, thinking_placeholder, wrap_lines


def test_clip_short():
    assert clip_line("こんにちは") == "こんにちは"


def test_clip_long():
    out = clip_line("あ" * 40, 8)
    assert out == "あああああああ…"
    assert len(out) == 8


def test_wrap_fits_screen():
    lines = wrap_lines("こんにちは！どうぞよろしくお願いします。", 12, 3)
    assert "".join(lines).startswith("こんにちは")
    assert all(len(x) <= 12 for x in lines)


def test_chat_screen_four_lines_max():
    lines = chat_screen("こんにちわ", "あ" * 40)
    assert len(lines) == 4
    assert lines[0] == "こんにちわ"
    assert lines[-1].endswith("…")


def test_echo_skips_thinking():
    assert thinking_placeholder("echo") is False
    assert thinking_placeholder("openai") is True
