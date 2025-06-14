from __future__ import annotations

from typing import Callable
import pexpect


def _await_input(child: pexpect.spawn, buffer: str, callback: Callable[[str], str]) -> tuple[str, str]:
    """Return output and updated buffer when an input prompt is detected."""

    if buffer and not buffer.endswith("\n"):
        try:
            child.read_nonblocking(size=1, timeout=0.1)
        except pexpect.TIMEOUT:
            user_input = callback(buffer)
            child.sendline(user_input)
            return buffer + "\n", ""
        except pexpect.EOF:
            return buffer, ""
    return "", buffer


def run_interactive(child: pexpect.spawn, input_callback: Callable[[str], str]) -> str:
    """Capture interactive command output using ``input_callback`` for prompts."""

    output_parts: list[str] = []
    buffer = ""
    while True:
        try:
            data = child.read_nonblocking(size=1024, timeout=0.1)
            buffer += data
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                output_parts.append(line + "\n")
        except pexpect.TIMEOUT:
            out, buffer = _await_input(child, buffer, input_callback)
            if out:
                output_parts.append(out)
            continue
        except pexpect.EOF:
            output_parts.append(buffer)
            break
    child.wait()
    child.close()
    return "".join(output_parts)

