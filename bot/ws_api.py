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
        payload: dict[str, object] = {
            "command": "team_chat",
            "args": {"prompt": prompt},
        }
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

            while True:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=timeout)
                except asyncio.TimeoutError as exc:
                    raise RuntimeError("Server did not respond in time") from exc

                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    self._log.debug("Ignoring non-JSON response: %s", raw)
                    continue

                if "result" in data or "error" in data:
                    return data

        raise RuntimeError("Server closed connection without a result")

    async def vm_execute_stream(
        self,
        command: str,
        *,
        user: str,
        session: str,
        think: bool = False,
    ) -> AsyncIterator[str]:
        """Yield output from ``command`` executed in the VM."""

        uri = self._build_uri(user, session, think)
        payload = {"command": "vm_execute_stream", "args": {"command": command}}
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps(payload))
            async for msg in ws:
                yield msg

    async def vm_execute(
        self,
        command: str,
        *,
        user: str,
        session: str,
        think: bool = False,
        timeout: int | None = None,
    ) -> str:
        """Return final output from ``command`` executed in the VM."""

        params: dict[str, object] = {"command": command}
        if timeout is not None:
            params["timeout"] = timeout
        resp = await self.request(
            "vm_execute",
            user=user,
            session=session,
            think=think,
            **params,
        )
        return str(resp.get("result", ""))

    async def vm_send_input(
        self,
        data: str,
        *,
        user: str,
        session: str,
        think: bool = False,
    ) -> None:
        """Send additional input to the user's VM shell."""

        await self.request(
            "vm_input",
            user=user,
            session=session,
            think=think,
            data=data,
        )

    async def list_dir(
        self,
        path: str,
        *,
        user: str,
        session: str,
        think: bool = False,
    ) -> list[tuple[str, bool]]:
        """Return directory listing for ``path`` inside the VM."""

        resp = await self.request(
            "list_dir",
            user=user,
            session=session,
            think=think,
            path=path,
        )
        result = resp.get("result", [])
        return [(name, bool(is_dir)) for name, is_dir in result]

    async def read_file(
        self,
        path: str,
        *,
        user: str,
        session: str,
        think: bool = False,
    ) -> str:
        """Return the contents of ``path`` from the VM."""

        resp = await self.request(
            "read_file",
            user=user,
            session=session,
            think=think,
            path=path,
        )
        return str(resp.get("result", ""))

    async def write_file(
        self,
        path: str,
        content: str,
        *,
        user: str,
        session: str,
        think: bool = False,
    ) -> str:
        """Write ``content`` to ``path`` in the VM and return server message."""

        resp = await self.request(
            "write_file",
            user=user,
            session=session,
            think=think,
            path=path,
            content=content,
        )
        return str(resp.get("result", ""))

    async def download_file(
        self,
        path: str,
        *,
        user: str,
        session: str,
        dest: str | None = None,
        think: bool = False,
    ) -> str:
        """Retrieve ``path`` from the VM and return the host destination path."""

        resp = await self.request(
            "download_file",
            user=user,
            session=session,
            think=think,
            path=path,
            dest=dest,
        )
        return str(resp.get("result", ""))

    async def delete_path(
        self,
        path: str,
        *,
        user: str,
        session: str,
        think: bool = False,
    ) -> str:
        """Remove ``path`` from the VM and return server message."""

        resp = await self.request(
            "delete_path",
            user=user,
            session=session,
            think=think,
            path=path,
        )
        return str(resp.get("result", ""))

    async def send_notification(
        self,
        message: str,
        *,
        user: str,
        session: str,
        think: bool = False,
    ) -> None:
        """Send a notification to the VM."""

        await self.request(
            "send_notification",
            user=user,
            session=session,
            think=think,
            message=message,
        )


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
