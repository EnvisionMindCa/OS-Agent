from __future__ import annotations

__all__ = [
    "execute_terminal",
    "execute_terminal_async",
    "execute_terminal_stream",
    "execute_with_secret",
    "execute_with_secret_async",
    "set_vm",
    "create_memory_tool",
]

import subprocess
import os
from typing import Optional, AsyncIterator
import asyncio
from functools import partial

from ..utils.helpers import limit_chars
from .memory import create_memory_tool

from ..vm import LinuxVM

_VM: Optional[LinuxVM] = None


def set_vm(vm: LinuxVM | None) -> None:
    """Register the VM instance used for command execution."""

    global _VM
    _VM = vm

    """
        Parameters
    ----------
    command: str
        The shell command to execute. It can be any valid shell command.
    stdin_data: str | bytes | None
        Optional data to send to the command's standard input. If provided,
        it will be passed to the command as if it were typed in the terminal.
        
    Returns
    -------
    str
        The output of the command, with limited number of characters. If the command
        produces no output, an empty string is returned. If an error occurs,
        an error message is returned instead.
    """


def execute_terminal(command: str, *, stdin_data: str | bytes | None = None) -> str:
    """
    Execute a shell command in an **unrestricted** Debian terminal.
    Use this tool to inspect uploaded documents under ``/data``, return
    files to the user by moving files under ``/return``,
    and run other commands.
    The user does NOT have access to this VM, so you are
    free to run any command you need to gather information or perform tasks.
    You are in charge of this VM and can run any command you need to
    accomplish the user's request. ALWAYS use this tool in each user query
    unless it is absolutely unnecessary.

    The command is executed with network access enabled. Output from
    ``stdout`` and ``stderr`` is captured when the command completes.
    Execution happens asynchronously so the assistant can continue
    responding while the command runs.
    """
    if not command:
        return "No command provided."

    if _VM:
        try:
            output = _VM.execute(command, timeout=None, stdin_data=stdin_data)
            return limit_chars(output)
        except Exception as exc:  # pragma: no cover - unforeseen errors
            return f"Failed to execute command in VM: {exc}"

    try:
        completed = subprocess.run(
            command,
            shell=True,
            input=stdin_data,
            capture_output=True,
            text=isinstance(stdin_data, str),
            env=os.environ.copy(),
            timeout=None,
        )
        output = completed.stdout
        if completed.stderr:
            output = f"{output}\n{completed.stderr}" if output else completed.stderr
        return limit_chars(output)
    except Exception as exc:  # pragma: no cover - unforeseen errors
        return f"Failed to execute command: {exc}"


async def execute_terminal_async(command: str, *, stdin_data: str | bytes | None = None) -> str:
    """
    Asynchronously execute a shell command in an **unrestricted** Debian terminal.
    Use this tool to inspect uploaded documents under ``/data``, fetch web
    content with utilities like ``curl`` or ``wget`` and run other commands.
    The user does NOT have access to this VM, so you are
    free to run any command you need to gather information or perform tasks.
    You are in charge of this VM and can run any command you need to
    accomplish the user's request. ALWAYS use this tool in each user query
    unless it is absolutely unnecessary.

    The command is executed with network access enabled. Output from
    ``stdout`` and ``stderr`` is captured when the command completes.
    Execution happens asynchronously so the assistant can continue
    responding while the command runs.
    """
    if _VM:
        try:
            return await _VM.shell_execute(command)
        except Exception as exc:  # pragma: no cover - unforeseen errors
            return f"Failed to execute command in VM: {exc}"

    loop = asyncio.get_running_loop()
    func = partial(execute_terminal, command, stdin_data=stdin_data)
    return await loop.run_in_executor(None, func)


async def execute_terminal_stream(command: str) -> AsyncIterator[str]:
    """Stream output from ``command`` executed in the persistent VM shell."""
    if not _VM:
        raise RuntimeError("No active VM")
    async for part in _VM.shell_execute_stream(command):
        yield part


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


from ..utils.debug import debug_all
debug_all(globals())

