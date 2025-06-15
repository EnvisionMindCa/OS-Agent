from __future__ import annotations

from ..chat import ChatSession
from ..config import OLLAMA_HOST, MODEL_NAME, SOLO_SYSTEM_PROMPT
from ..tools import execute_terminal

__all__ = ["SoloChatSession"]


class SoloChatSession(ChatSession):
    """Single-agent chat session using :data:`SOLO_SYSTEM_PROMPT`."""

    def __init__(
        self,
        user: str = "default",
        session: str = "default",
        host: str = OLLAMA_HOST,
        model: str = MODEL_NAME,
        *,
        think: bool = True,
    ) -> None:
        super().__init__(
            user=user,
            session=session,
            host=host,
            model=model,
            system_prompt=SOLO_SYSTEM_PROMPT,
            tools=[execute_terminal],
            think=think,
        )

from ..utils.debug import debug_all
debug_all(globals())

