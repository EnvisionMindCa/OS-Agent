from __future__ import annotations

__all__ = ["execute_terminal"]

import subprocess
from typing import Final


def execute_terminal(command: str, *, timeout: int = 3) -> str:
    """
    Execute a shell command in a Windows PowerShell terminal.
    Use this tool to run various commands.

    The command is executed with network access enabled. Output from both
    ``stdout`` and ``stderr`` is captured and returned. Commands are killed if
    they exceed ``timeout`` seconds.
    """
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
