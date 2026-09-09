def clip_line(text: str, limit: int = 12) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def wrap_lines(text: str, width: int = 12, max_lines: int = 3) -> list[str]:
    text = " ".join((text or "").split())
    if not text:
        return [""]
    parts = [text[i : i + width] for i in range(0, len(text), width)]
    if len(parts) > max_lines:
        parts = parts[:max_lines]
        last = parts[-1]
        parts[-1] = last[: width - 1] + "…" if len(last) >= width else last + "…"
    return parts


def chat_screen(user: str, reply: str) -> list[str]:
    return [clip_line(user, 12), *wrap_lines(reply, 12, 3)]


def thinking_placeholder(backend: str) -> bool:
    """echo is instant; an intermediate screen just looks frozen."""
    return backend != "echo"
