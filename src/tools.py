from __future__ import annotations

__all__ = [
    "execute_terminal",
    "execute_terminal_async",
    "set_vm",
    "send_agent_message",
    "send_agent_message_async",
]

import subprocess
import os
from typing import Optional
import asyncio
import functools

from .utils import limit_chars
from .agent_comm import MessageRouter

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
    about any detail. The user does NOT have access to this VM, so you are
    free to run any command you need to gather information or perform tasks.
    You are in charge of this VM and can run any command you need to
    accomplish the user's request.

    The command is executed with network access enabled. Output from
    ``stdout`` and ``stderr`` is captured when the command completes.
    Execution happens asynchronously so the assistant can continue
    responding while the command runs.
    """
    if not command:
        return "No command provided."

    if _VM:
        try:
            output = _VM.execute(command, timeout=None)
            return limit_chars(output)
        except Exception as exc:  # pragma: no cover - unforeseen errors
            return f"Failed to execute command in VM: {exc}"

    try:
        completed = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            timeout=None,
        )
        output = completed.stdout
        if completed.stderr:
            output = f"{output}\n{completed.stderr}" if output else completed.stderr
        return limit_chars(output)
    except Exception as exc:  # pragma: no cover - unforeseen errors
        return f"Failed to execute command: {exc}"


async def execute_terminal_async(command: str) -> str:
    """Asynchronously execute a shell command."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, execute_terminal, command)


def send_agent_message(
    to: str,
    message: str,
    urgency: str | None = None,
    cc: str | None = None,
    *,
    from_agent: str,
    user: str,
) -> str:
    """Send ``message`` from ``from_agent`` to another agent.

    The message is queued for the receiving agent without interrupting its
    current generation.
    """

    payload = {"from": from_agent, "to": to, "content": message}
    if urgency:
        payload["urgency"] = urgency
    if cc:
        payload["cc"] = cc
    MessageRouter.send(user, to, payload)
    return f"Message queued for {to}"


async def send_agent_message_async(
    to: str,
    message: str,
    urgency: str | None = None,
    cc: str | None = None,
    *,
    from_agent: str,
    user: str,
) -> str:
    """Async wrapper around :func:`send_agent_message`."""

    loop = asyncio.get_running_loop()
    func = functools.partial(
        send_agent_message,
        to,
        message,
        urgency,
        cc,
        from_agent=from_agent,
        user=user,
    )
    return await loop.run_in_executor(None, func)

