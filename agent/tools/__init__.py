

__all__ = [
    "execute_terminal",
    "execute_terminal_async",
    "execute_with_secret",
    "execute_with_secret_async",
    "set_vm",
    "close_terminal_session",
]

import asyncio
from functools import partial
from typing import Optional

from ..utils.helpers import limit_chars
from ..vm import LinuxVM
from .terminal_session import TerminalSession


_VM: Optional[LinuxVM] = None
_SESSION: Optional[TerminalSession] = None


def set_vm(vm: LinuxVM | None) -> None:
    """Register the VM instance used for command execution."""

    global _VM, _SESSION
    _VM = vm
    if _SESSION is not None:
        _SESSION.close()
        _SESSION = None



def _get_session() -> TerminalSession:
    """Return the current ``TerminalSession`` creating one if needed."""

    global _SESSION
    if _SESSION is None:
        _SESSION = TerminalSession(_VM)
    return _SESSION


def close_terminal_session() -> None:
    """Terminate the active terminal session if any."""

    global _SESSION
    if _SESSION is not None:
        _SESSION.close()
        _SESSION = None


def execute_terminal(
    command: str,
    *,
    stdin_data: str | bytes | None = None,
) -> str:
    """
    Execute a shell command in an **unrestricted** Debian terminal.
    Use this tool to inspect uploaded documents under ``/data``, fetch web
    content with utilities like ``curl`` or ``wget`` and run other commands.
    The user does NOT have access to this VM, so you are
    free to run any command you need to gather information or perform tasks.
    You are in charge of this VM and can run any command you need to
    accomplish the user's request. ALWAYS use this tool in each user query
    unless it is absolutely unnecessary.

    The command is executed with network access enabled. A full terminal
    transcript including prompts, the command itself and any output is
    returned (up to 10,000 characters). Execution happens asynchronously so
    the assistant can continue responding while the command runs.
    """
    if not command and stdin_data is None:
        return "No command provided."

    session = _get_session()
    try:
        return session.execute(command, stdin_data=stdin_data)
    except Exception as exc:  # pragma: no cover - unforeseen errors
        session.close()
        return f"Failed to execute command: {exc}"


async def execute_terminal_async(
    command: str,
    *,
    stdin_data: str | bytes | None = None,
) -> str:
    """Asynchronously execute a shell command."""
    loop = asyncio.get_running_loop()
    func = partial(
        execute_terminal,
        command,
        stdin_data=stdin_data,
    )
    return await loop.run_in_executor(None, func)


def execute_with_secret(
    command: str,
    secret_name: str,
    *,
    prompt: str | None = None,
) -> str:
    """Execute ``command`` passing the retrieved secret to ``stdin``."""
    from ..utils.secrets import get_secret

    secret = get_secret(secret_name, prompt)
    return execute_terminal(command, stdin_data=f"{secret}\n")


async def execute_with_secret_async(
    command: str,
    secret_name: str,
    *,
    prompt: str | None = None,
) -> str:
    """Asynchronously execute ``command`` with a secret fed to ``stdin``."""
    loop = asyncio.get_running_loop()
    func = partial(execute_with_secret, command, secret_name, prompt=prompt)
    return await loop.run_in_executor(None, func)

