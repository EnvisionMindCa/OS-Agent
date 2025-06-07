from __future__ import annotations

__all__ = ["execute_terminal", "execute_terminal_async", "set_vm"]

import subprocess
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
    Use this tool to inspect uploaded documents under ``/data`` or run other commands.

    The command is executed with network access enabled. Output from both
    ``stdout`` and ``stderr`` is captured and returned. Commands are killed if
    they exceed 30 seconds.
    """
    timeout = 30
    if not command:
        return "No command provided."

    if _VM:
        try:
            return _VM.execute(command, timeout=timeout)
        except Exception as exc:  # pragma: no cover - unforeseen errors
            return f"Failed to execute command in VM: {exc}"

    try:
        completed = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return f"Command timed out after {timeout}s: {exc.cmd}"
    except Exception as exc:  # pragma: no cover - unforeseen errors
        return f"Failed to execute command: {exc}"

    output = completed.stdout
    if completed.stderr:
        output = f"{output}\n{completed.stderr}" if output else completed.stderr
    return output.strip()


async def execute_terminal_async(command: str) -> str:
    """Asynchronously execute a shell command."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, execute_terminal, command)
