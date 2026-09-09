from llm import OPENAI_DEFAULT, openai_base, ollama_base


def test_openai_ignores_ollama_default_port():
    assert openai_base("http://127.0.0.1:11434") == OPENAI_DEFAULT
    assert openai_base("") == OPENAI_DEFAULT


def test_openai_custom_proxy():
    assert openai_base("https://example.invalid/v1") == "https://example.invalid/v1"


def test_ollama_default():
    assert ollama_base("") == "http://127.0.0.1:11434"
