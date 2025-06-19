from __future__ import annotations

"""Command dispatchers for :mod:`agent.server`.

This module exposes a single :func:`dispatch_command` coroutine used by the
:class:`~agent.server.websocket.AgentWebSocketServer` to execute API functions
based on JSON requests received from clients.
"""

from typing import Any, AsyncIterator, Iterable
import json

from ..simple import (
    solo_chat,
    team_chat,
    upload_document,
    list_dir,
    read_file,
    write_file,
    delete_path,
    vm_execute,
    send_notification,
)
from ..config import Config
from ..sessions.team import TeamChatSession


async def _yield_stream(stream: AsyncIterator[str]) -> AsyncIterator[str]:
    """Yield all elements from ``stream``."""

    async for part in stream:
        if part is None:
            continue
        yield part


async def dispatch_command(
    command: str,
    params: dict[str, Any] | None,
    *,
    user: str,
    session: str,
    think: bool,
    config: Config,
    chat: TeamChatSession | None = None,
) -> AsyncIterator[str]:
    """Dispatch a command and yield results as strings.

    Parameters
    ----------
    command:
        Name of the API function to invoke.
    params:
        Optional dictionary of keyword arguments for the command.
    user, session, think, config:
        Context passed to API functions when required.
    chat:
        Active :class:`TeamChatSession` for ``team_chat`` commands. May be
        ``None`` for other calls.
    """

    params = params or {}

    if command in {"team_chat", "chat"}:
        prompt = str(params.get("prompt", ""))
        if chat is not None:
            async for part in _yield_stream(chat.chat_stream(prompt)):
                yield part
        else:
            async for part in _yield_stream(
                team_chat(
                    prompt,
                    user=user,
                    session=session,
                    think=think,
                    config=config,
                )
            ):
                yield part
        return

    if command == "solo_chat":
        prompt = str(params.get("prompt", ""))
        async for part in _yield_stream(
            solo_chat(
                prompt,
                user=user,
                session=session,
                think=think,
                config=config,
            )
        ):
            yield part
        return

    if command == "upload_document":
        file_path = str(params["file_path"])
        result = await upload_document(
            file_path,
            user=user,
            session=session,
            config=config,
        )
        yield json.dumps({"result": result})
        return

    if command == "list_dir":
        path = str(params["path"])
        listing = await list_dir(path, user=user)
        yield json.dumps({"result": list(listing)})
        return

    if command == "read_file":
        path = str(params["path"])
        content = await read_file(path, user=user)
        yield json.dumps({"result": content})
        return

    if command == "write_file":
        path = str(params["path"])
        content = str(params.get("content", ""))
        result = await write_file(path, content, user=user)
        yield json.dumps({"result": result})
        return

    if command == "delete_path":
        path = str(params["path"])
        result = await delete_path(path, user=user)
        yield json.dumps({"result": result})
        return

    if command == "vm_execute":
        cmd = str(params["command"])
        timeout = params.get("timeout")
        if timeout is not None:
            timeout = int(timeout)
        result = await vm_execute(cmd, user=user, timeout=timeout)
        yield json.dumps({"result": result})
        return

    if command == "send_notification":
        message = str(params["message"])
        send_notification(message, user=user)
        yield json.dumps({"result": "ok"})
        return

    raise ValueError(f"Unknown command: {command}")


__all__ = ["dispatch_command"]
