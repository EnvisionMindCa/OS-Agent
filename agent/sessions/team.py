from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import AsyncIterator, Optional

from ..chat import ChatSession
from ..config import (
    Config,
    DEFAULT_CONFIG,
)
from ..tools import execute_terminal

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
        prompt = parent._config.mini_agent_prompt.format(
            name=name, details=details, context=context
        )
        self.session = ChatSession(
            user=parent._user.username,
            session=f"{parent._session_name}-{name}",
            host=parent._config.ollama_host,
            model=parent._model,
            system_prompt=prompt,
            tools=[execute_terminal],
            think=parent._think,
            persist=False,
            config=parent._config,
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
            if self.parent._state == "idle":
                await self.parent._deliver_agent_messages()
        finally:
            self.task = None


class TeamChatSession(ChatSession):
    def __init__(
        self,
        user: str = "default",
        session: str = "default",
        host: str | None = None,
        model: str | None = None,
        *,
        think: bool = True,
        config: Config | None = None,
    ) -> None:
        config = config or DEFAULT_CONFIG
        super().__init__(
            user=user,
            session=session,
            host=host or config.ollama_host,
            model=model or config.model_name,
            system_prompt=config.system_prompt,
            tools=[execute_terminal, spawn_agent, send_to_agent],
            think=think,
            config=config,
        )
        self._session_name = session
        self._agents: dict[str, _MiniAgent] = {}
        self._to_master: asyncio.Queue[tuple[str, str]] = asyncio.Queue()

    async def __aenter__(self) -> "TeamChatSession":
        await super().__aenter__()
        set_team(self)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        set_team(None)
        await self._destroy_agents()
        await super().__aexit__(exc_type, exc, tb)

    async def spawn_agent(self, name: str, details: str = "", context: str = "") -> str:
        if name in self._agents:
            return f"Agent {name} already exists"
        if len(self._agents) >= self._config.max_mini_agents:
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

    async def _deliver_agent_messages(self) -> None:
        while not self._to_master.empty():
            name, msg = await self._to_master.get()
            self._add_tool_message(
                self._conversation, self._messages, name, msg
            )

    async def _destroy_agents(self) -> None:
        for name, agent in list(self._agents.items()):
            await agent.stop()
            self._agents.pop(name, None)

    async def chat_stream(self, prompt: str, *, extra: dict[str, str] | None = None) -> AsyncIterator[str]:
        await self._deliver_agent_messages()
        async for part in super().chat_stream(prompt, extra=extra):
            yield part
        await self._deliver_agent_messages()
        await self._destroy_agents()

