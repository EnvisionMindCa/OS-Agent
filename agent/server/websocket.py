from __future__ import annotations

import asyncio
from contextlib import suppress
from urllib.parse import parse_qs, urlparse
import json
import base64

from websockets.exceptions import ConnectionClosed
from websockets.server import WebSocketServer, WebSocketServerProtocol, serve

from ..vm import VMRegistry

from ..sessions.team import TeamChatSession
from ..config import Config, DEFAULT_CONFIG
from ..utils.logging import get_logger
from .endpoints import dispatch_command


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
                returned = self._vm.fetch_returned_files()
                for n in notes:
                    await self._notification_queue.put(n)
                for r in returned:
                    try:
                        data = r.read_bytes()
                        encoded = base64.b64encode(data).decode()
                    except Exception as exc:  # pragma: no cover
                        self._log.error(
                            "Failed to read returned file %s: %s", r, exc
                        )
                        continue
                    try:
                        r.unlink()
                    except Exception as exc:  # pragma: no cover
                        self._log.warning(
                            "Failed to delete returned file %s: %s", r, exc
                        )
                    payload = json.dumps(
                        {"returned_file": r.name, "data": encoded}
                    )
                    await self._notification_queue.put(payload)
                    await self._out_q.put(payload)
                if (
                    (notes or returned)
                    and self._state == "idle"
                    and self._prompt_queue.empty()
                    and (not self._worker or self._worker.done())
                ):
                    async for part in self._deliver_notifications_stream():
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
        """Stop the server, close connections, and cleanup VMs."""
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        VMRegistry.shutdown_all()

    async def _handler(self, ws: WebSocketServerProtocol) -> None:
        params = parse_qs(urlparse(ws.path).query)
        user = params.get("user", ["default"])[0]
        session = params.get("session", ["default"])[0]
        think_param = params.get("think", ["true"])[0]
        think = think_param.lower() not in ("false", "0", "no")

        out_q: asyncio.Queue[str] = asyncio.Queue()
        chat = StreamingTeamChatSession(
            user=user,
            session=session,
            think=think,
            output_queue=out_q,
            config=self._config,
        )
        async with chat:
            sender = asyncio.create_task(self._sender(ws, out_q))
            try:
                async for message in ws:
                    await self._process(
                        chat,
                        message,
                        out_q,
                        user,
                        session,
                        think,
                    )
            except ConnectionClosed:  # pragma: no cover - client disconnect
                pass
            finally:
                sender.cancel()
                with suppress(asyncio.CancelledError):
                    await sender

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

    async def _sender(
        self, ws: WebSocketServerProtocol, out_q: asyncio.Queue[str]
    ) -> None:
        try:
            while True:
                part = await out_q.get()
                await ws.send(part)
        except ConnectionClosed:  # pragma: no cover - client disconnect
            pass


__all__ = ["AgentWebSocketServer"]
