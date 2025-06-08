from __future__ import annotations

from typing import Dict
from contextlib import AsyncExitStack

from .chat import ChatSession
from .config import AGENT_PROMPTS
from .history import load_history
from .schema import Msg


class TeamChatSession:
    """Manage a group of cooperative agents for a single user."""

    def __init__(self, user: str = "default", session: str = "default") -> None:
        self._user = user
        self._session = session
        self._agents: Dict[str, ChatSession] = {
            name: ChatSession(
                user=user,
                session=f"{session}-{name}",
                agent_name=name,
                system_prompt=prompt,
            )
            for name, prompt in AGENT_PROMPTS.items()
        }
        self._stack: AsyncExitStack | None = None

    async def __aenter__(self) -> "TeamChatSession":
        self._stack = AsyncExitStack()
        for agent in self._agents.values():
            await self._stack.enter_async_context(agent)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._stack:
            await self._stack.aclose()
            self._stack = None

    def get_history(self, agent: str) -> list[Msg]:
        """Return the chat history for ``agent`` from the database."""

        session = self._agents.get(agent)
        if not session:
            raise KeyError(agent)
        return load_history(session._conversation)

    async def chat_stream(self, prompt: str):
        """Send ``prompt`` to the planner agent and stream its reply."""
        planner = self._agents["planner"]
        async for part in planner.chat_stream(prompt):
            yield part
        # Allow other agents to process queued messages in the background
        for name, agent in self._agents.items():
            if name == "planner":
                continue
            await agent._flush_incoming()
