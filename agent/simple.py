from __future__ import annotations

from typing import AsyncIterator, Iterable
import base64
import json
import shlex

from .sessions.solo import SoloChatSession
from .sessions.team import TeamChatSession
from .vm import VMRegistry

__all__ = [
    "solo_chat",
    "team_chat",
    "upload_document",
    "list_dir",
    "read_file",
    "write_file",
    "delete_path",
    "vm_execute",
    "send_input",
]

_SESSIONS: dict[tuple[str, str], SoloChatSession | TeamChatSession] = {}


async def send_input(value: str, *, user: str = "default", session: str = "default") -> None:
    """Provide input to a running chat session."""

    chat = _SESSIONS.get((user, session))
    if chat is None:
        raise RuntimeError("No active session")
    await chat.send_user_input(value)


async def solo_chat(
    prompt: str,
    *,
    user: str = "default",
    session: str = "default",
    think: bool = True,
) -> AsyncIterator[str]:
    async with SoloChatSession(user=user, session=session, think=think) as chat:
        _SESSIONS[(user, session)] = chat
        try:
            async for part in chat.chat_stream(prompt):
                yield part
        finally:
            _SESSIONS.pop((user, session), None)


async def team_chat(
    prompt: str,
    *,
    user: str = "default",
    session: str = "default",
    think: bool = True,
) -> AsyncIterator[str]:
    async with TeamChatSession(user=user, session=session, think=think) as chat:
        _SESSIONS[(user, session)] = chat
        try:
            async for part in chat.chat_stream(prompt):
                yield part
        finally:
            _SESSIONS.pop((user, session), None)


async def upload_document(
    file_path: str,
    *,
    user: str = "default",
    session: str = "default",
) -> str:
    """Upload ``file_path`` for access inside the VM.

    The file becomes available under ``/data`` in the VM.
    """
    async with SoloChatSession(user=user, session=session, think=False) as chat:
        return chat.upload_document(file_path)


async def vm_execute(
    command: str,
    *,
    user: str = "default",
    timeout: int | None = 5,
) -> str:
    """Execute ``command`` inside ``user``'s VM and return the output."""
    vm = VMRegistry.acquire(user)
    try:
        return await vm.execute_async(command, timeout=timeout)
    finally:
        VMRegistry.release(user)


async def list_dir(path: str, *, user: str = "default") -> Iterable[tuple[str, bool]]:
    """Return an iterable of ``(name, is_dir)`` for ``path`` inside the VM."""
    output = await vm_execute(f"ls -1ap {shlex.quote(path)}", user=user)
    if output.startswith("ls:"):
        return []
    rows = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line in (".", ".."):
            continue
        is_dir = line.endswith("/")
        name = line[:-1] if is_dir else line
        rows.append((name, is_dir))
    return rows


async def read_file(path: str, *, user: str = "default") -> str:
    """Return the contents of ``path`` from the VM."""
    return await vm_execute(f"cat {shlex.quote(path)}", user=user)


async def write_file(path: str, content: str, *, user: str = "default") -> str:
    """Write ``content`` to ``path`` inside the VM."""
    encoded = base64.b64encode(content.encode()).decode()
    cmd = (
        "python -c 'import base64,os; "
        f"open({json.dumps(path)}, \"wb\").write(base64.b64decode({json.dumps(encoded)}))'"
    )
    await vm_execute(cmd, user=user)
    return "Saved"


async def delete_path(path: str, *, user: str = "default") -> str:
    """Delete a file or directory at ``path`` inside the VM."""
    cmd = (
        f"bash -c 'if [ -d {shlex.quote(path)} ]; then rm -rf {shlex.quote(path)} && echo Deleted; "
        f"elif [ -e {shlex.quote(path)} ]; then rm -f {shlex.quote(path)} && echo Deleted; "
        f"else echo File not found; fi'"
    )
    return await vm_execute(cmd, user=user)
