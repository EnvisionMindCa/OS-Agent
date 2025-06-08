from __future__ import annotations

import asyncio
from typing import Dict, Tuple
from threading import Lock


class MessageRouter:
    """Route messages between agents using per-agent asyncio queues."""

    _queues: Dict[Tuple[str, str], asyncio.Queue[dict]] = {}
    _lock = Lock()

    @classmethod
    def register(cls, user: str, agent: str) -> asyncio.Queue[dict]:
        """Return the queue for ``agent`` under ``user``, creating it if needed."""
        key = (user, agent)
        with cls._lock:
            queue = cls._queues.get(key)
            if queue is None:
                queue = asyncio.Queue()
                cls._queues[key] = queue
        return queue

    @classmethod
    def send(cls, user: str, agent: str, message: dict) -> None:
        """Enqueue ``message`` for ``agent`` belonging to ``user``."""
        queue = cls.register(user, agent)
        queue.put_nowait(message)
