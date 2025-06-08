from __future__ import annotations

__all__ = ["execute_terminal", "execute_terminal_async", "set_vm"]

import subprocess
import os
from typing import Optional
import asyncio

from .vm import LinuxVM

_VM: Optional[LinuxVM] = None


def set_vm(vm: LinuxVM | None) -> None:
    """Register the VM instance used for command execution."""

    global _VM
    _VM = vm


def execute_terminal(command: str) -> str:
    """
    Execute a shell command in a Ubuntu terminal.
    Use this tool to inspect uploaded documents under ``/data``, fetch web
    content with utilities like ``curl`` or ``wget`` and run other commands.
    The assistant must call this tool to search the internet whenever unsure
    about any detail.

    The command is executed with network access enabled. It runs in the
    background without a timeout so the assistant can continue responding
    while the command executes.
    """
    if not command:
        return "No command provided."

    if _VM:
        try:
            return _VM.execute(command, detach=True)
        except Exception as exc:  # pragma: no cover - unforeseen errors
            return f"Failed to execute command in VM: {exc}"

    try:
        subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=os.environ.copy(),
        )
        return "Command started in background."
    except Exception as exc:  # pragma: no cover - unforeseen errors
        return f"Failed to execute command: {exc}"


async def execute_terminal_async(command: str) -> str:
    """Asynchronously execute a shell command."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, execute_terminal, command)
