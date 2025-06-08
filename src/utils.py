from __future__ import annotations

__all__ = ["limit_chars"]


def limit_chars(text: str, limit: int = 10_000) -> str:
    """Return at most ``limit`` characters from ``text``.

    Earlier characters are stripped when the text exceeds the limit.
    A short notice is prepended indicating the amount removed.
    """
    text = text.strip()
    if len(text) <= limit:
        return text

    truncated = len(text) - limit
    return f"(output truncated, {truncated} characters hidden)\n{text[-limit:]}"

