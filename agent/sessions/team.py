from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import AsyncIterator, Optional

from ..chat import ChatSession
from ..config import (
    OLLAMA_HOST,
    MODEL_NAME,
    SYSTEM_PROMPT,
    MINI_AGENT_PROMPT,
    MAX_MINI_AGENTS,
)
from ..tools import execute_terminal
from ..db import db
from ..chat.messages import store_tool_message

__all__ = [
    "TeamChatSession",
    "set_team",
]

_TEAM: Optional["TeamChatSession"] = None


def set_team(team: "TeamChatSession" | None) -> None:
    global _TEAM
    _TEAM = team


async def spawn_agent(name: str, details: str = "", context: str = "") -> str:
    if _TEAM is None:
        return "No active team"
    return await _TEAM.spawn_agent(name, details, context)


async def send_to_agent(name: str, message: str) -> str:
    if _TEAM is None:
        return "No active team"
    return await _TEAM.queue_message_to_agent(name, message, enqueue=False)


class _MiniAgent:
    def __init__(self, parent: "TeamChatSession", name: str, details: str, context: str) -> None:
        self.parent = parent
        self.name = name
        prompt = MINI_AGENT_PROMPT.format(name=name, details=details, context=context)
        self.session = ChatSession(
            user=parent._user,
            session=f"{parent._session_name}-{name}",
            host=parent._host,
            model=parent._model,
            system_prompt=prompt,
            tools=[execute_terminal],
            think=parent._think,
            persist=False,
        )
        self.queue: asyncio.Queue[tuple[str, asyncio.Future[str], bool]] = asyncio.Queue()
        self.task: asyncio.Task | None = None

    async def start(self) -> None:
        await self.session.__aenter__()

    async def stop(self) -> None:
        if self.task and not self.task.done():
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
        await self.session.__aexit__(None, None, None)

    async def queue_message(self, message: str, *, enqueue: bool = True) -> str:
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[str] = loop.create_future()
        await self.queue.put((message, fut, enqueue))
        if not self.task or self.task.done():
            self.task = asyncio.create_task(self._process())
        return await fut

    async def _process(self) -> None:
        try:
            while not self.queue.empty():
                msg, fut, enqueue = await self.queue.get()
                self.session._messages.append({"role": "tool", "name": "senior", "content": msg})
                parts: list[str] = []
                async for part in self.session.continue_stream():
                    if part:
                        parts.append(part)
                result = "\n".join(parts)
                if enqueue and result.strip():
                    await self.parent._to_master.put((self.name, result))
                if not fut.done():
                    fut.set_result(result)
            if self.parent.master._state == "idle":
                await self.parent._deliver_agent_messages()
        finally:
            self.task = None


class TeamChatSession:
    def __init__(
        self,
        user: str = "default",
        session: str = "default",
        host: str = OLLAMA_HOST,
        model: str = MODEL_NAME,
        *,
        think: bool = True,
    ) -> None:
        self._user = user
        self._session_name = session
        self._host = host
        self._model = model
        self._think = think
        self._agents: dict[str, _MiniAgent] = {}
        self._to_master: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
        self.master = ChatSession(
            user=user,
            session=session,
            host=host,
            model=model,
            system_prompt=SYSTEM_PROMPT,
            tools=[execute_terminal, spawn_agent, send_to_agent],
            think=think,
        )

    async def __aenter__(self) -> "TeamChatSession":
        await self.master.__aenter__()
        set_team(self)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        set_team(None)
        await self._destroy_agents()
        await self.master.__aexit__(exc_type, exc, tb)

    def upload_document(self, file_path: str) -> str:
        return self.master.upload_document(file_path)

    async def spawn_agent(self, name: str, details: str = "", context: str = "") -> str:
        if name in self._agents:
            return f"Agent {name} already exists"
        if len(self._agents) >= MAX_MINI_AGENTS:
            return "Agent limit reached"
        agent = _MiniAgent(self, name, details, context)
        await agent.start()
        self._agents[name] = agent
        return f"Spawned {name}"

    async def queue_message_to_agent(self, name: str, message: str, *, enqueue: bool = True) -> str:
        agent = self._agents.get(name)
        if not agent:
            return f"Agent {name} not found"
        return await agent.queue_message(message, enqueue=enqueue)

    async def _process_agents(self) -> None:
        for agent in list(self._agents.values()):
            if agent.task and not agent.task.done():
                await agent.task

    async def _deliver_agent_messages(self) -> None:
        while not self._to_master.empty():
            name, msg = await self._to_master.get()
            self.master._messages.append({"role": "tool", "name": name, "content": msg})
            store_tool_message(self.master._conversation, name, msg)

    async def _destroy_agents(self) -> None:
        for name, agent in list(self._agents.items()):
            await agent.stop()
            self._agents.pop(name, None)

    async def chat_stream(self, prompt: str, *, extra: dict[str, str] | None = None) -> AsyncIterator[str]:
        await self._deliver_agent_messages()
        async for part in self.master.chat_stream(prompt, extra=extra):
            yield part
        await self._deliver_agent_messages()
        await self._destroy_agents()

