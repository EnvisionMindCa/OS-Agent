from __future__ import annotations

import asyncio
from typing import AsyncIterator

from .debug import debug_all

__all__ = ["limit_chars", "coalesce_stream"]


def limit_chars(text: str, limit: int = 10_000) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text

    truncated = len(text) - limit
    return f"(output truncated, {truncated} characters hidden)\n{text[-limit:]}"


async def coalesce_stream(
    stream: AsyncIterator[str],
    *,
    interval: float = 0.1,
    max_size: int = 1024,
) -> AsyncIterator[str]:
    """Yield buffered chunks from ``stream`` to avoid message spam."""

    buffer: list[str] = []
    size = 0
    last = asyncio.get_running_loop().time()
    async for chunk in stream:
        buffer.append(chunk)
        size += len(chunk)
        now = asyncio.get_running_loop().time()
        if "\n" in chunk or size >= max_size or now - last >= interval:
            yield "".join(buffer)
            buffer.clear()
            size = 0
            last = now
    if buffer:
        yield "".join(buffer)


debug_all(globals())
