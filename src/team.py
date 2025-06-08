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

    async def _collect(self, stream) -> str:
        """Return the concatenated text from an async iterator."""

        parts: list[str] = []
        async for chunk in stream:
            parts.append(chunk)
        return "".join(parts).strip()

    async def chat_stream(self, prompt: str):
        """Coordinate all agents and stream a single final reply."""

        planner = self._agents["planner"]
        plan = await self._collect(planner.chat_stream(prompt))

        researcher = self._agents["researcher"]
        research_prompt = (
            f"Planner notes:\n{plan}\n\nGather any information needed to complete the task."
        )
        research = await self._collect(researcher.chat_stream(research_prompt))

        developer = self._agents["developer"]
        dev_prompt = (
            f"Planner notes:\n{plan}\n\nResearch summary:\n{research}\n\nProvide code or steps required to fulfil the request."
        )
        dev_notes = await self._collect(developer.chat_stream(dev_prompt))

        reviewer = self._agents["reviewer"]
        review_prompt = (
            "Craft the final response for the user using the following inputs:\n"
            f"Planner notes:\n{plan}\n\nResearch summary:\n{research}\n\nDeveloper notes:\n{dev_notes}"
        )
        final_answer = await self._collect(reviewer.chat_stream(review_prompt))

        for agent in self._agents.values():
            await agent._flush_incoming()

        yield final_answer
