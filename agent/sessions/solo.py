from __future__ import annotations

from ..chat import ChatSession
from ..config import Config, DEFAULT_CONFIG
from ..tools import execute_terminal

__all__ = ["SoloChatSession"]


class SoloChatSession(ChatSession):
    """Single-agent chat session using :data:`SOLO_SYSTEM_PROMPT`."""

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
            system_prompt=config.solo_system_prompt,
            tools=[execute_terminal],
            think=think,
            config=config,
        )

from ..utils.debug import debug_all
debug_all(globals())

