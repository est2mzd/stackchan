from intent import route_utterance


def test_clock_mode():
    assert route_utterance("時計モード") == "clock"
    assert route_utterance(" 時計 モード ") == "clock"


def test_chat_mode():
    assert route_utterance("会話モード") == "chat"
    assert route_utterance("戻って") == "chat"


def test_other_goes_to_llm():
    assert route_utterance("こんにちは") == "utterance"
