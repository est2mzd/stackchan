from __future__ import annotations


def normalize_ja(text: str) -> str:
    return (
        text.replace(" ", "")
        .replace("　", "")
        .replace("。", "")
        .replace("、", "")
        .strip()
    )


def route_utterance(text: str) -> str:
    """Return clock, chat, or utterance."""
    n = normalize_ja(text)
    if "時計モード" in n or n in ("時計", "とけい"):
        return "clock"
    if "会話モード" in n or n in ("戻って", "もどって"):
        return "chat"
    return "utterance"
