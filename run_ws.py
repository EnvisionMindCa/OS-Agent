from __future__ import annotations

"""Interactive WebSocket client for streaming chat messages.

This script connects to an :class:`~agent.server.AgentWebSocketServer` instance
and keeps the WebSocket connection open indefinitely. User prompts are sent as
soon as they are entered while LLM responses and VM notifications are streamed
back immediately. The connection remains open so that notifications can be
delivered even when the user is idle.
"""

import argparse
import asyncio
from contextlib import suppress

import websockets

from agent.utils.logging import get_logger

_LOG = get_logger(__name__)


async def _receiver(ws: websockets.WebSocketClientProtocol) -> None:
    """Print all messages received from the server."""

    try:
        async for msg in ws:
            print(msg, end="", flush=True)
    except websockets.ConnectionClosed:
        _LOG.info("Connection closed by server")


async def chat(uri: str, message: str) -> None:
    """Connect to ``uri`` and interactively exchange chat messages."""

    async with websockets.connect(uri) as ws:
        _LOG.info("Connected to %s", uri)
        if message:
            await ws.send(message)

        recv_task = asyncio.create_task(_receiver(ws))
        try:
            loop = asyncio.get_running_loop()
            while True:
                prompt = await loop.run_in_executor(None, input, "> ")
                await ws.send(prompt)
        except KeyboardInterrupt:
            pass
        finally:
            recv_task.cancel()
            with suppress(asyncio.CancelledError):
                await recv_task


def _build_uri(host: str, port: int, user: str, session: str, think: bool) -> str:
    think_val = "true" if think else "false"
    return f"ws://{host}:{port}/?user={user}&session={session}&think={think_val}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Interactive WebSocket client")
    parser.add_argument("--host", default="localhost", help="Server host")
    parser.add_argument("--port", type=int, default=8765, help="Server port")
    parser.add_argument("--user", default="demo", help="Username")
    parser.add_argument("--session", default="ws", help="Session identifier")
    think_group = parser.add_mutually_exclusive_group()
    think_group.add_argument(
        "--think",
        dest="think",
        action="store_true",
        help="Enable model thinking (default)",
    )
    think_group.add_argument(
        "--no-think",
        dest="think",
        action="store_false",
        help="Disable model thinking",
    )
    parser.set_defaults(think=True)
    parser.add_argument(
        "--message",
        default="Hello from the client!",
        help="Optional message to send on connect",
    )
    args = parser.parse_args()

    uri = _build_uri(args.host, args.port, args.user, args.session, args.think)
    asyncio.run(chat(uri, args.message))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass

