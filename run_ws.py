from __future__ import annotations

"""Command line WebSocket client for :mod:`agent.server` endpoints.

The script exposes convenience subcommands matching the available WebSocket
API. It supports interactive team chat as well as file and VM operations. The
``solo_chat`` endpoint is intentionally omitted.
"""

import argparse
import asyncio
from contextlib import suppress

import json
import websockets

from agent.utils.logging import get_logger

_LOG = get_logger(__name__)


async def _receiver(ws: websockets.WebSocketClientProtocol) -> None:
    """Print all messages received from ``ws``."""

    try:
        async for msg in ws:
            print(msg, end="", flush=True)
    except websockets.ConnectionClosed:
        _LOG.info("Connection closed by server")


async def chat(uri: str, message: str) -> None:
    """Interactively exchange team chat messages on ``uri``."""

    async with websockets.connect(uri) as ws:
        _LOG.info("Connected to %s", uri)
        if message:
            await ws.send(json.dumps({"command": "team_chat", "args": {"prompt": message}}))

        recv_task = asyncio.create_task(_receiver(ws))
        try:
            loop = asyncio.get_running_loop()
            while True:
                prompt = await loop.run_in_executor(None, input, "> ")
                await ws.send(json.dumps({"command": "team_chat", "args": {"prompt": prompt}}))
        except KeyboardInterrupt:
            pass
        finally:
            recv_task.cancel()
            with suppress(asyncio.CancelledError):
                await recv_task


def _build_uri(host: str, port: int, user: str, session: str, think: bool) -> str:
    think_val = "true" if think else "false"
    return f"ws://{host}:{port}/?user={user}&session={session}&think={think_val}"


async def request(uri: str, command: str, **params: object) -> None:
    """Send a single command and print the server response."""

    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"command": command, "args": params}))
        try:
            while True:
                message = await ws.recv()
                print(message, end="", flush=True)
                break
        except websockets.ConnectionClosed:
            _LOG.info("Connection closed by server")


async def _main(args: argparse.Namespace) -> None:
    uri = _build_uri(args.host, args.port, args.user, args.session, args.think)
    cmd = args.command

    if cmd == "chat":
        await chat(uri, args.message)
        return

    if cmd == "upload":
        await request(uri, "upload_document", file_path=args.path)
        return

    if cmd == "list":
        await request(uri, "list_dir", path=args.path)
        return

    if cmd == "read":
        await request(uri, "read_file", path=args.path)
        return

    if cmd == "write":
        await request(uri, "write_file", path=args.path, content=args.content)
        return

    if cmd == "delete":
        await request(uri, "delete_path", path=args.path)
        return

    if cmd == "exec":
        await request(uri, "vm_execute", command=args.command_str, timeout=args.timeout)
        return

    if cmd == "notify":
        await request(uri, "send_notification", message=args.message)


def main() -> None:
    parser = argparse.ArgumentParser(description="WebSocket API client")
    parser.add_argument("--host", default="localhost", help="Server host")
    parser.add_argument("--port", type=int, default=8765, help="Server port")
    parser.add_argument("--user", default="demo", help="Username")
    parser.add_argument("--session", default="ws", help="Session identifier")
    think_group = parser.add_mutually_exclusive_group()
    think_group.add_argument("--think", dest="think", action="store_true", help="Enable model thinking (default)")
    think_group.add_argument("--no-think", dest="think", action="store_false", help="Disable model thinking")
    parser.set_defaults(think=True)

    sub = parser.add_subparsers(dest="command", required=True)

    chat_p = sub.add_parser("chat", help="Interactive team chat")
    chat_p.add_argument("--message", default="", help="Initial prompt")

    up_p = sub.add_parser("upload", help="Upload document")
    up_p.add_argument("path", help="Path to local file")

    list_p = sub.add_parser("list", help="List directory")
    list_p.add_argument("path", help="Path in VM")

    read_p = sub.add_parser("read", help="Read file")
    read_p.add_argument("path", help="Path in VM")

    write_p = sub.add_parser("write", help="Write file")
    write_p.add_argument("path", help="Path in VM")
    write_p.add_argument("content", help="Content to write")

    del_p = sub.add_parser("delete", help="Delete path")
    del_p.add_argument("path", help="Path in VM")

    exec_p = sub.add_parser("exec", help="Execute command in VM")
    exec_p.add_argument("command_str", help="Command to run")
    exec_p.add_argument("--timeout", type=int, default=None, help="Execution timeout")

    notify_p = sub.add_parser("notify", help="Send notification")
    notify_p.add_argument("message", help="Notification message")

    args = parser.parse_args()
    asyncio.run(_main(args))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass

