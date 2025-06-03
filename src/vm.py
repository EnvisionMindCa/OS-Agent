from __future__ import annotations

from typing import Optional
import subprocess
import uuid

from .log import get_logger

_LOG = get_logger(__name__)


class LinuxVM:
    """Manage a lightweight Linux VM using Docker."""

    def __init__(self, image: str = "ubuntu:latest") -> None:
        self._image = image
        self._name = f"chat-vm-{uuid.uuid4().hex[:8]}"
        self._running = False

    def start(self) -> None:
        """Start the VM if it is not already running."""
        if self._running:
            return

        try:
            subprocess.run(
                ["docker", "pull", self._image],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            subprocess.run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    self._name,
                    self._image,
                    "sleep",
                    "infinity",
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self._running = True
        except Exception as exc:  # pragma: no cover - runtime failures
            _LOG.error("Failed to start VM: %s", exc)
            raise RuntimeError(f"Failed to start VM: {exc}") from exc

    def execute(self, command: str, *, timeout: int = 3) -> str:
        """Execute a command inside the running VM."""
        if not self._running:
            raise RuntimeError("VM is not running")

        try:
            completed = subprocess.run(
                [
                    "docker",
                    "exec",
                    self._name,
                    "bash",
                    "-lc",
                    command,
                ],
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

    def stop(self) -> None:
        """Terminate the VM if running."""
        if not self._running:
            return

        subprocess.run(
            ["docker", "rm", "-f", self._name],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self._running = False

    def __enter__(self) -> "LinuxVM":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()
