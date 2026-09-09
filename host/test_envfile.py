from pathlib import Path

from envfile import load_env_file


def test_load_env_file_sets_missing_key(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    p = tmp_path / ".env"
    p.write_text("OPENAI_API_KEY=sk-test\n")
    load_env_file(p)
    import os

    assert os.environ["OPENAI_API_KEY"] == "sk-test"
