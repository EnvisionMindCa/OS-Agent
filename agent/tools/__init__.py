from __future__ import annotations

__all__ = [
    "execute_terminal",
    "execute_terminal_async",
    "execute_with_secret",
    "execute_with_secret_async",
    "set_vm",
]

import subprocess
import os
from typing import Optional
import asyncio
from functools import partial

from ..utils.helpers import limit_chars

from ..vm import LinuxVM

_VM: Optional[LinuxVM] = None


def set_vm(vm: LinuxVM | None) -> None:
    """Register the VM instance used for command execution."""

    global _VM
    _VM = vm


def execute_terminal(command: str, *, stdin_data: str | bytes | None = None) -> str:
    """
    Execute a shell command in a Ubuntu terminal.
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
    """Asynchronously execute a shell command."""
    loop = asyncio.get_running_loop()
    func = partial(execute_terminal, command, stdin_data=stdin_data)
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

