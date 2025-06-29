from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from ..utils.debug import debug_all


@dataclass
class SessionState:
    """Container for per-conversation state."""

    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    status: str = "idle"
    tool_task: asyncio.Task | None = None


_session_states: dict[int, SessionState] = {}


def get_state(conv_id: int) -> SessionState:
    """Return existing state for ``conv_id`` or create a new one."""

    state = _session_states.get(conv_id)
    if state is None:
        state = SessionState()
        _session_states[conv_id] = state
    return state


debug_all(globals())
