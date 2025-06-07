from __future__ import annotations

from typing import Iterator

import discord

MAX_CONTENT_LENGTH = 2000


def chunk_message(content: str, limit: int = MAX_CONTENT_LENGTH) -> Iterator[str]:
    """Yield pieces of ``content`` each under ``limit`` characters."""
    for i in range(0, len(content), limit):
        yield content[i : i + limit]


async def send_reply(
    message: discord.Message, content: str, *, mention_author: bool = False
) -> None:
    """Reply to ``message`` with ``content``, splitting if needed."""
    chunks = list(chunk_message(content))
    if not chunks:
        return

    await message.reply(chunks[0], mention_author=mention_author)
    for chunk in chunks[1:]:
        await message.channel.send(chunk)
