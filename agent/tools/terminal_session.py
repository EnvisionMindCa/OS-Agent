from __future__ import annotations

from typing import Optional
import os
import platform
import io
import threading
import pexpect

from ..utils.helpers import limit_chars
from ..vm import LinuxVM, VM_CMD


class TerminalSession:
    """Manage an interactive shell either locally or inside a VM."""

    def __init__(self, vm: Optional[LinuxVM] = None) -> None:
        self._vm = vm
        self._lock = threading.Lock()
        self._child, self._prompt = self._spawn_shell()

    # ------------------------------------------------------------------
    def _spawn_shell(self) -> tuple[pexpect.spawn, str | pexpect.re]:
        if self._vm:
            if not self._vm._running:  # type: ignore[attr-defined]
                raise RuntimeError("VM is not running")
            prompt_env = self._vm._prompt_env or ""  # type: ignore[attr-defined]
            prompt_re = self._vm._prompt_re or ""  # type: ignore[attr-defined]
            child = pexpect.spawn(
                VM_CMD,
                [
                    "exec",
                    "-i",
                    "-t",
                    self._vm._name,  # type: ignore[attr-defined]
                    "bash",
                    "--noprofile",
                    "--norc",
                    "-i",
                ],
                env={"PS1": prompt_env},
                encoding="utf-8",
                echo=True,
            )
            child.expect(prompt_re)
            return child, prompt_re
        user = os.environ.get("USER", "user")
        host = platform.node().split(".")[0]
        cwd = os.path.basename(os.getcwd())
        prompt = f"{user}@{host} {cwd} % "
        child = pexpect.spawn(
            "bash",
            ["--noprofile", "--norc", "-i"],
            env={"PS1": prompt},
            encoding="utf-8",
            echo=True,
        )
        child.expect_exact(prompt)
        return child, prompt

    # ------------------------------------------------------------------
    def execute(self, command: str, *, stdin_data: str | bytes | None = None, timeout: int | None = 2) -> str:
        """Send ``command`` or ``stdin_data`` to the shell and return output."""
        with self._lock:
            log = io.StringIO()
            self._child.logfile_read = log

            if command:
                self._child.sendline(command)
            if stdin_data is not None:
                if isinstance(stdin_data, bytes):
                    stdin_data = stdin_data.decode()
                self._child.send(stdin_data)
            try:
                if isinstance(self._prompt, str):
                    self._child.expect_exact(self._prompt, timeout=timeout)
                else:
                    self._child.expect(self._prompt, timeout=timeout)
            except pexpect.TIMEOUT:
                pass
            return limit_chars(log.getvalue())

    # ------------------------------------------------------------------
    def close(self) -> None:
        with self._lock:
            if self._child.isalive():
                self._child.close(force=True)
