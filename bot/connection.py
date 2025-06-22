from __future__ import annotations

import json
from typing import AsyncIterator

import websockets

from .ws_client import WSApiClient

class WSConnection:
    """Persistent connection wrapper for :mod:`agent.server`."""

    def __init__(
        self,
        client: WSApiClient,
        *,
        user: str,
        session: str,
        think: bool = True,
    ) -> None:
        self._client = client
        self._user = user
        self._session = session
        self._think = think
        self._ws: websockets.WebSocketClientProtocol | None = None

    @property
    def user(self) -> str:
        return self._user

    @property
    def session(self) -> str:
        return self._session

    async def connect(self) -> None:
        uri = self._client._build_uri(self._user, self._session, self._think)
        self._ws = await websockets.connect(uri)

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None

    async def send(self, command: str, **params: object) -> None:
        if self._ws is None:
            raise RuntimeError("Connection not established")
        await self._ws.send(json.dumps({"command": command, "args": params}))

    async def __aiter__(self) -> AsyncIterator[str]:
        if self._ws is None:
            raise RuntimeError("Connection not established")
        async for msg in self._ws:
            yield msg

    async def send_input(self, data: str) -> None:
        """Send ``data`` to the connected VM shell."""

        await self.send("vm_input", data=data)

    async def send_keys(self, data: str, *, delay: float = 0.05) -> None:
        """Simulate typing ``data`` on the connected VM shell."""

        await self.send("vm_keys", data=data, delay=delay)

__all__ = ["WSConnection"]

