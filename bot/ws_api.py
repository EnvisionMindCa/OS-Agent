from __future__ import annotations

import asyncio
import json
from typing import AsyncIterator

import websockets

from agent.utils.logging import get_logger


class WSApiClient:
    """Simple client for :mod:`agent.server` WebSocket API."""

    def __init__(self, host: str = "localhost", port: int = 8765) -> None:
        self._host = host
        self._port = port
        self._log = get_logger(__name__)

    def _build_uri(self, user: str, session: str, think: bool) -> str:
        think_val = "true" if think else "false"
        return f"ws://{self._host}:{self._port}/?user={user}&session={session}&think={think_val}"

    async def team_chat_stream(
        self,
        prompt: str,
        *,
        user: str,
        session: str,
        think: bool = True,
        extra: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> AsyncIterator[str]:
        """Yield chat responses for ``prompt`` sent to the server.

        Parameters
        ----------
        timeout:
            Seconds to wait for the next message before concluding the
            stream. Increase this if the model takes a long time to
            produce a reply.
        """

        uri = self._build_uri(user, session, think)
        payload: dict[str, object] = {"command": "team_chat", "args": {"prompt": prompt}}
        if extra:
            payload["args"].update(extra)

        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps(payload))
            while True:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
                except asyncio.TimeoutError:
                    break
                else:
                    yield msg

    async def request(
        self,
        command: str,
        *,
        user: str,
        session: str,
        think: bool = True,
        timeout: float = 10.0,
        **params: object,
    ) -> object:
        """Send a command and return the parsed JSON response."""

        uri = self._build_uri(user, session, think)
        payload = {"command": command, "args": params}

        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps(payload))
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
            except asyncio.TimeoutError as exc:
                raise RuntimeError("Server did not respond in time") from exc

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            self._log.error("Invalid JSON response: %s", raw)
            raise RuntimeError("Invalid server response")


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

