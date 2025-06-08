from __future__ import annotations

import asyncio
from typing import AsyncIterator, Optional

from .chat import ChatSession
from .config import OLLAMA_HOST, MODEL_NAME, SYSTEM_PROMPT, JUNIOR_PROMPT
from .tools import execute_terminal
from .db import Message as DBMessage

__all__ = [
    "TeamChatSession",
    "send_to_junior",
    "send_to_junior_async",
    "set_team",
]

_TEAM: Optional["TeamChatSession"] = None


def set_team(team: "TeamChatSession" | None) -> None:
    global _TEAM
    _TEAM = team


async def send_to_junior(message: str) -> str:
    """Forward ``message`` to the junior agent and return a status string."""

    if _TEAM is None:
        return "No active team"

    _TEAM.queue_message_to_junior(message)
    return "Message sent to junior"


# Backwards compatibility ---------------------------------------------------

send_to_junior_async = send_to_junior


class TeamChatSession:
    def __init__(
        self,
        user: str = "default",
        session: str = "default",
        host: str = OLLAMA_HOST,
        model: str = MODEL_NAME,
    ) -> None:
        self._to_junior: asyncio.Queue[str] = asyncio.Queue()
        self._to_senior: asyncio.Queue[str] = asyncio.Queue()
        self._junior_task: asyncio.Task | None = None
        self.senior = ChatSession(
            user=user,
            session=session,
            host=host,
            model=model,
            system_prompt=SYSTEM_PROMPT,
            tools=[execute_terminal, send_to_junior],
        )
        self.junior = ChatSession(
            user=user,
            session=f"{session}-junior",
            host=host,
            model=model,
            system_prompt=JUNIOR_PROMPT,
            tools=[execute_terminal],
        )

    async def __aenter__(self) -> "TeamChatSession":
        await self.senior.__aenter__()
        await self.junior.__aenter__()
        set_team(self)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        set_team(None)
        await self.senior.__aexit__(exc_type, exc, tb)
        await self.junior.__aexit__(exc_type, exc, tb)

    def upload_document(self, file_path: str) -> str:
        return self.senior.upload_document(file_path)

    def queue_message_to_junior(self, message: str) -> None:
        self._to_junior.put_nowait(message)
        if not self._junior_task or self._junior_task.done():
            self._junior_task = asyncio.create_task(self._process_junior())

    async def _process_junior(self) -> None:
        try:
            while not self._to_junior.empty():
                msg = await self._to_junior.get()
                self.junior._messages.append({"role": "tool", "name": "senior", "content": msg})
                DBMessage.create(conversation=self.junior._conversation, role="tool", content=msg)
                parts: list[str] = []
                async for part in self.junior.continue_stream():
                    if part:
                        parts.append(part)
                result = "\n".join(parts)
                if result.strip():
                    await self._to_senior.put(result)

            if self.senior._state == "idle":
                await self._deliver_junior_messages()
        finally:
            self._junior_task = None

    async def _deliver_junior_messages(self) -> None:
        while not self._to_senior.empty():
            msg = await self._to_senior.get()
            self.senior._messages.append({"role": "tool", "name": "junior", "content": msg})
            DBMessage.create(conversation=self.senior._conversation, role="tool", content=msg)

    async def chat_stream(self, prompt: str) -> AsyncIterator[str]:
        await self._deliver_junior_messages()
        async for part in self.senior.chat_stream(prompt):
            yield part
        await self._deliver_junior_messages()
