from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from urllib.parse import parse_qs, urlparse

from websockets.exceptions import ConnectionClosed
from websockets.server import WebSocketServer, WebSocketServerProtocol, serve

from ..config import Config, DEFAULT_CONFIG
from ..sessions.team import TeamChatSession
from ..vm import VMRegistry
from ..utils.logging import get_logger
from .endpoints import dispatch_command


class AgentWebSocketServer:
    """WebSocket server that streams agent responses and VM output."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8765, *, config: Config | None = None) -> None:
        self._host = host
        self._port = port
        self._config = config or DEFAULT_CONFIG
        self._server: WebSocketServer | None = None
        self._log = get_logger(__name__)

    async def start(self) -> None:
        """Start accepting WebSocket connections."""
        self._server = await serve(self._handler, self._host, self._port)
        self._log.info("Server listening on %s:%d", self._host, self._port)

    async def stop(self) -> None:
        """Stop the server and clean up running VMs."""
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        VMRegistry.shutdown_all()

    # ---------------------------------------------------------------
    async def _handler(self, ws: WebSocketServerProtocol) -> None:
        params = parse_qs(urlparse(ws.path).query)
        user = params.get("user", ["default"])[0]
        session = params.get("session", ["default"])[0]
        think_val = params.get("think", ["true"])[0]
        think = think_val.lower() not in {"false", "0", "no"}

        out_q: asyncio.Queue[str] = asyncio.Queue()
        chat = TeamChatSession(user=user, session=session, think=think, config=self._config)
        async with chat:
            await self._send_notifications(chat, out_q)
            tasks = [
                asyncio.create_task(self._sender(ws, out_q)),
                asyncio.create_task(self._notification_poller(chat, out_q)),
            ]
            try:
                async for message in ws:
                    await self._process(chat, message, out_q, user, session, think)
            except ConnectionClosed:
                pass
            finally:
                for t in tasks:
                    t.cancel()
                with suppress(asyncio.CancelledError):
                    await asyncio.gather(*tasks)

    # ---------------------------------------------------------------
    async def _process(
        self,
        chat: TeamChatSession,
        message: str,
        out_q: asyncio.Queue[str],
        user: str,
        session: str,
        think: bool,
    ) -> None:
        try:
            request = json.loads(message)
        except json.JSONDecodeError:
            request = {"command": "team_chat", "args": {"prompt": message}}

        command = str(request.get("command", "team_chat"))
        params = request.get("args", {})

        try:
            async for part in dispatch_command(
                command,
                params,
                user=user,
                session=session,
                think=think,
                config=self._config,
                chat=chat,
            ):
                await out_q.put(part)
        except Exception as exc:  # pragma: no cover - runtime errors
            await out_q.put(json.dumps({"error": str(exc)}))

    async def _sender(self, ws: WebSocketServerProtocol, out_q: asyncio.Queue[str]) -> None:
        try:
            while True:
                msg = await out_q.get()
                await ws.send(msg)
        except ConnectionClosed:
            pass

    async def _notification_poller(self, chat: TeamChatSession, out_q: asyncio.Queue[str]) -> None:
        try:
            while True:
                await asyncio.sleep(self._config.notification_poll_interval)
                await self._send_notifications(chat, out_q)
        except asyncio.CancelledError:
            pass

    async def _send_notifications(self, chat: TeamChatSession, out_q: asyncio.Queue[str]) -> None:
        for part in await chat.poll_notifications():
            await out_q.put(part)


__all__ = ["AgentWebSocketServer"]
