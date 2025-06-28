from __future__ import annotations

import os
import pty
import select
import subprocess
import struct
import fcntl
import termios
from typing import Optional

import pyte

from .logging import get_logger

__all__ = ["PTYProcess"]


class PTYProcess:
    """Run a command in a persistent pseudo terminal."""

    def __init__(self, cmd: str | list[str], *, env: Optional[dict[str, str]] = None,
                 cols: int = 80, rows: int = 24) -> None:
        self._cmd = cmd
        self._env = env or os.environ.copy()
        self._env.setdefault("TERM", self._env.get("TERM", "xterm-256color"))
        self._cols = cols
        self._rows = rows
        self._fd: Optional[int] = None
        self._proc: Optional[subprocess.Popen] = None
        self._screen = pyte.Screen(cols, rows)
        self._stream = pyte.Stream(self._screen)
        self._log = get_logger(__name__)

    # ------------------------------------------------------------------
    def spawn(self) -> None:
        """Start the process attached to a PTY."""
        if self._proc:
            return
        master_fd, slave_fd = pty.openpty()
        self._set_winsize(master_fd, self._rows, self._cols)
        self._proc = subprocess.Popen(
            self._cmd,
            shell=isinstance(self._cmd, str),
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            env=self._env,
            close_fds=True,
        )
        os.close(slave_fd)
        self._fd = master_fd
        self._log.debug("Spawned process %s with pid %s", self._cmd, self._proc.pid)

    # ------------------------------------------------------------------
    def _set_winsize(self, fd: int, rows: int, cols: int) -> None:
        size = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, size)

    # ------------------------------------------------------------------
    def send(self, data: str | bytes) -> None:
        """Write ``data`` to the PTY."""
        if self._fd is None:
            raise RuntimeError("Process not started")
        if isinstance(data, str):
            data = data.encode()
        os.write(self._fd, data)

    # ------------------------------------------------------------------
    def read(self, timeout: float = 0.1) -> str:
        """Read available output from the PTY."""
        if self._fd is None:
            return ""
        output = []
        r, _, _ = select.select([self._fd], [], [], timeout)
        if r:
            data = os.read(self._fd, 4096)
            self._stream.feed(data)
            output.append(data.decode(errors="replace"))
        return "".join(output)

    # ------------------------------------------------------------------
    @property
    def screen(self) -> str:
        """Return the formatted screen buffer."""
        return "\n".join(self._screen.display)

    # ------------------------------------------------------------------
    def is_alive(self) -> bool:
        """Return ``True`` if the process is still running."""
        return bool(self._proc and self._proc.poll() is None)

    # ------------------------------------------------------------------
    def terminate(self) -> None:
        """Terminate the running process."""
        if self._proc and self.is_alive():
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except Exception:  # pragma: no cover - unforeseen errors
                self._proc.kill()
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        self._proc = None
        self._screen.reset()
        self._log.debug("Process terminated")


