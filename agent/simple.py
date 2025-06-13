from __future__ import annotations

import asyncio
from typing import AsyncIterator

from .sessions.solo import SoloChatSession
from .sessions.team import TeamChatSession

__all__ = [
    "solo_chat",
    "team_chat",
    "solo_chat_stream",
    "team_chat_stream",
]


async def solo_chat_stream(
    prompt: str,
    *,
    user: str = "default",
    session: str = "default",
    think: bool = True,
) -> AsyncIterator[str]:
    """Stream the assistant's response using :class:`SoloChatSession`."""

    async with SoloChatSession(user=user, session=session, think=think) as chat:
        async for part in chat.chat_stream(prompt):
            yield part


async def team_chat_stream(
    prompt: str,
    *,
    user: str = "default",
    session: str = "default",
    think: bool = True,
) -> AsyncIterator[str]:
    """Stream the assistant's response using :class:`TeamChatSession`."""

    async with TeamChatSession(user=user, session=session, think=think) as chat:
        async for part in chat.chat_stream(prompt):
            yield part


async def solo_chat(
    prompt: str,
    *,
    user: str = "default",
    session: str = "default",
    think: bool = True,
) -> str:
    """Return the full response from a :class:`SoloChatSession`."""

    parts: list[str] = []
    async for part in solo_chat_stream(
        prompt, user=user, session=session, think=think
    ):
        if part:
            parts.append(part)
    return "\n".join(parts)


async def team_chat(
    prompt: str,
    *,
    user: str = "default",
    session: str = "default",
    think: bool = True,
) -> str:
    """Return the full response from a :class:`TeamChatSession`."""

    parts: list[str] = []
    async for part in team_chat_stream(
        prompt, user=user, session=session, think=think
    ):
        if part:
            parts.append(part)
    return "\n".join(parts)
