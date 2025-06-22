from __future__ import annotations

"""Command dispatchers for :mod:`agent.server`.

This module exposes a single :func:`dispatch_command` coroutine used by the
:class:`~agent.server.websocket.AgentWebSocketServer` to execute API functions
based on JSON requests received from clients.
"""

from typing import Any, AsyncIterator, Awaitable, Callable, Iterable
import json
import base64

from ..api import (
    team_chat,
    upload_document,
    upload_data,
    list_dir,
    read_file,
    write_file,
    delete_path,
    download_file,
    vm_execute,
    vm_execute_stream,
    vm_send_input,
    send_notification,
    list_sessions,
    list_sessions_info,
    list_documents,
    get_memory,
    set_memory,
    reset_memory,
    restart_terminal,
)
from ..config import Config
from ..sessions.team import TeamChatSession


async def _yield_stream(stream: AsyncIterator[str]) -> AsyncIterator[str]:
    """Yield all elements from ``stream``."""

    async for part in stream:
        if part is None:
            continue
        yield part


Handler = Callable[
    [dict[str, Any], str, str, bool, Config, TeamChatSession | None],
    Awaitable[AsyncIterator[str]] | AsyncIterator[str],
]


async def _team_chat_handler(
    params: dict[str, Any],
    user: str,
    session: str,
    think: bool,
    config: Config,
    chat: TeamChatSession | None,
) -> AsyncIterator[str]:
    prompt = str(params.get("prompt", ""))
    if chat is not None:
        stream = chat.chat_stream(prompt)
    else:
        stream = team_chat(prompt, user=user, session=session, think=think, config=config)
    async for part in _yield_stream(stream):
        yield part




async def _upload_document_handler(
    params: dict[str, Any],
    user: str,
    session: str,
    think: bool,
    config: Config,
    chat: TeamChatSession | None,
) -> AsyncIterator[str]:
    file_data = params.get("file_data")
    file_name = params.get("file_name")
    if file_data is not None:
        if not file_name:
            raise ValueError("file_name required when file_data provided")
        data = base64.b64decode(file_data)
        result = await upload_data(data, file_name, user=user, session=session, config=config)
    else:
        file_path = str(params["file_path"])
        result = await upload_document(file_path, user=user, session=session, config=config)
    yield json.dumps({"result": result})


async def _list_dir_handler(
    params: dict[str, Any],
    user: str,
    session: str,
    think: bool,
    config: Config,
    chat: TeamChatSession | None,
) -> AsyncIterator[str]:
    path = str(params["path"])
    listing = await list_dir(path, user=user, config=config)
    yield json.dumps({"result": list(listing)})


async def _read_file_handler(
    params: dict[str, Any],
    user: str,
    session: str,
    think: bool,
    config: Config,
    chat: TeamChatSession | None,
) -> AsyncIterator[str]:
    path = str(params["path"])
    content = await read_file(path, user=user, config=config)
    yield json.dumps({"result": content})


async def _write_file_handler(
    params: dict[str, Any],
    user: str,
    session: str,
    think: bool,
    config: Config,
    chat: TeamChatSession | None,
) -> AsyncIterator[str]:
    path = str(params["path"])
    content = str(params.get("content", ""))
    result = await write_file(path, content, user=user, config=config)
    yield json.dumps({"result": result})


async def _delete_path_handler(
    params: dict[str, Any],
    user: str,
    session: str,
    think: bool,
    config: Config,
    chat: TeamChatSession | None,
) -> AsyncIterator[str]:
    path = str(params["path"])
    result = await delete_path(path, user=user, config=config)
    yield json.dumps({"result": result})


async def _download_file_handler(
    params: dict[str, Any],
    user: str,
    session: str,
    think: bool,
    config: Config,
    chat: TeamChatSession | None,
) -> AsyncIterator[str]:
    path = str(params["path"])
    dest = params.get("dest")
    result = await download_file(path, user=user, dest=dest, config=config)
    yield json.dumps({"result": result})


async def _vm_execute_handler(
    params: dict[str, Any],
    user: str,
    session: str,
    think: bool,
    config: Config,
    chat: TeamChatSession | None,
) -> AsyncIterator[str]:
    cmd = str(params["command"])
    timeout = params.get("timeout")
    if timeout is not None:
        timeout = int(timeout)
    result = await vm_execute(cmd, user=user, timeout=timeout, config=config)
    yield json.dumps({"result": result})


async def _vm_execute_stream_handler(
    params: dict[str, Any],
    user: str,
    session: str,
    think: bool,
    config: Config,
    chat: TeamChatSession | None,
) -> AsyncIterator[str]:
    cmd = str(params["command"])
    raw = bool(params.get("raw", False))
    async for part in vm_execute_stream(
        cmd, user=user, config=config, raw=raw
    ):
        yield part


async def _vm_input_handler(
    params: dict[str, Any],
    user: str,
    session: str,
    think: bool,
    config: Config,
    chat: TeamChatSession | None,
) -> AsyncIterator[str]:
    data = params.get("data", "")
    simulate = bool(params.get("simulate_typing", False))
    delay = float(params.get("delay", 0.05))
    await vm_send_input(
        str(data),
        user=user,
        config=config,
        simulate_typing=simulate,
        delay=delay,
    )
    yield json.dumps({"result": "ok"})


async def _send_notification_handler(
    params: dict[str, Any],
    user: str,
    session: str,
    think: bool,
    config: Config,
    chat: TeamChatSession | None,
) -> AsyncIterator[str]:
    message = str(params["message"])
    send_notification(message, user=user, config=config)
    yield json.dumps({"result": "ok"})


async def _list_sessions_handler(
    params: dict[str, Any],
    user: str,
    session: str,
    think: bool,
    config: Config,
    chat: TeamChatSession | None,
) -> AsyncIterator[str]:
    sessions = await list_sessions(user)
    yield json.dumps({"result": sessions})


async def _list_sessions_info_handler(
    params: dict[str, Any],
    user: str,
    session: str,
    think: bool,
    config: Config,
    chat: TeamChatSession | None,
) -> AsyncIterator[str]:
    info = await list_sessions_info(user)
    yield json.dumps({"result": info})


async def _list_documents_handler(
    params: dict[str, Any],
    user: str,
    session: str,
    think: bool,
    config: Config,
    chat: TeamChatSession | None,
) -> AsyncIterator[str]:
    docs = await list_documents(user)
    yield json.dumps({"result": docs})


async def _get_memory_handler(
    params: dict[str, Any],
    user: str,
    session: str,
    think: bool,
    config: Config,
    chat: TeamChatSession | None,
) -> AsyncIterator[str]:
    memory = await get_memory(user)
    yield json.dumps({"result": memory})


async def _set_memory_handler(
    params: dict[str, Any],
    user: str,
    session: str,
    think: bool,
    config: Config,
    chat: TeamChatSession | None,
) -> AsyncIterator[str]:
    memory = str(params.get("memory", ""))
    result = await set_memory(user, memory)
    yield json.dumps({"result": result})


async def _reset_memory_handler(
    params: dict[str, Any],
    user: str,
    session: str,
    think: bool,
    config: Config,
    chat: TeamChatSession | None,
) -> AsyncIterator[str]:
    memory = await reset_memory(user)
    yield json.dumps({"result": memory})


async def _restart_terminal_handler(
    params: dict[str, Any],
    user: str,
    session: str,
    think: bool,
    config: Config,
    chat: TeamChatSession | None,
) -> AsyncIterator[str]:
    await restart_terminal(user=user, config=config)
    if chat is not None:
        await chat.send_notification("VM terminal restarted")
    yield json.dumps({"result": "restarted"})


_HANDLERS: dict[str, Callable[..., AsyncIterator[str]]] = {
    "team_chat": _team_chat_handler,
    "chat": _team_chat_handler,
    "upload_document": _upload_document_handler,
    "list_dir": _list_dir_handler,
    "read_file": _read_file_handler,
    "write_file": _write_file_handler,
    "delete_path": _delete_path_handler,
    "download_file": _download_file_handler,
    "vm_execute": _vm_execute_handler,
    "vm_execute_stream": _vm_execute_stream_handler,
    "vm_input": _vm_input_handler,
    "send_notification": _send_notification_handler,
    "list_sessions": _list_sessions_handler,
    "list_sessions_info": _list_sessions_info_handler,
    "list_documents": _list_documents_handler,
    "get_memory": _get_memory_handler,
    "set_memory": _set_memory_handler,
    "reset_memory": _reset_memory_handler,
    "restart_terminal": _restart_terminal_handler,
}


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
    """Dispatch a command and yield results as strings."""

    params = params or {}

    handler = _HANDLERS.get(command)
    if handler is None:
        raise ValueError(f"Unknown command: {command}")

    async for part in handler(params, user, session, think, config, chat):
        if part is None:
            continue
        yield part


__all__ = ["dispatch_command"]
