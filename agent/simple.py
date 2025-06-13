from __future__ import annotations

from typing import AsyncIterator

from .sessions.solo import SoloChatSession
from .sessions.team import TeamChatSession

__all__ = [
    "solo_chat",
    "team_chat"
]


async def solo_chat(
    prompt: str,
    *,
    user: str = "default",
    session: str = "default",
    think: bool = True,
) -> AsyncIterator[str]:
    async with SoloChatSession(user=user, session=session, think=think) as chat:
        async for part in chat.chat_stream(prompt):
            yield part


async def team_chat(
    prompt: str,
    *,
    user: str = "default",
    session: str = "default",
    think: bool = True,
) -> AsyncIterator[str]:
    async with TeamChatSession(user=user, session=session, think=think) as chat:
        async for part in chat.chat_stream(prompt):
            yield part
