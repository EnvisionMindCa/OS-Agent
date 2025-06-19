from __future__ import annotations

import asyncio
from contextlib import suppress
from urllib.parse import parse_qs, urlparse

from websockets.exceptions import ConnectionClosed
from websockets.server import WebSocketServer, WebSocketServerProtocol, serve

from .sessions.team import TeamChatSession
from .config import Config, DEFAULT_CONFIG
from .utils.logging import get_logger


class StreamingTeamChatSession(TeamChatSession):
    """Team chat session that pushes responses to an output queue."""

    def __init__(
        self,
        *,
        output_queue: asyncio.Queue[str],
        config: Config | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(config=config, **kwargs)
        self._out_q = output_queue

    async def _monitor_notifications(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._config.notification_poll_interval)
                if self._vm is None:
                    continue
                notes = self._vm.fetch_notifications()
                for note in notes:
                    async for part in self.send_notification_stream(note):
                        await self._out_q.put(part)
        except asyncio.CancelledError:  # pragma: no cover - lifecycle
            pass


class AgentWebSocketServer:
    """WebSocket server streaming chat responses and notifications."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8765,
        *,
        config: Config | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._config = config or DEFAULT_CONFIG
        self._log = get_logger(__name__)
        self._server: WebSocketServer | None = None

    async def start(self) -> None:
        """Start accepting websocket connections."""
        self._server = await serve(self._handler, self._host, self._port)
        self._log.info("Server listening on %s:%d", self._host, self._port)

    async def stop(self) -> None:
        """Stop the server and close all connections."""
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()

    async def _handler(self, ws: WebSocketServerProtocol) -> None:
        params = parse_qs(urlparse(ws.path).query)
        user = params.get("user", ["default"])[0]
        session = params.get("session", ["default"])[0]

        out_q: asyncio.Queue[str] = asyncio.Queue()
        chat = StreamingTeamChatSession(user=user, session=session, output_queue=out_q, config=self._config)
        async with chat:
            sender = asyncio.create_task(self._sender(ws, out_q))
            try:
                async for message in ws:
                    await self._process(chat, message, out_q)
            except ConnectionClosed:  # pragma: no cover - client disconnect
                pass
            finally:
                sender.cancel()
                with suppress(asyncio.CancelledError):
                    await sender

    async def _process(self, chat: TeamChatSession, prompt: str, out_q: asyncio.Queue[str]) -> None:
        async for part in chat.chat_stream(prompt):
            await out_q.put(part)

    async def _sender(self, ws: WebSocketServerProtocol, out_q: asyncio.Queue[str]) -> None:
        try:
            while True:
                part = await out_q.get()
                await ws.send(part)
        except ConnectionClosed:  # pragma: no cover - client disconnect
            pass


__all__ = ["AgentWebSocketServer"]

