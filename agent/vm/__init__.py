from __future__ import annotations

import subprocess
import asyncio
import os
import datetime
from functools import partial
from pathlib import Path

from threading import Lock

from ..config import (
    DEFAULT_CONFIG,
    Config,
)
from ..utils.helpers import limit_chars

from ..utils.logging import get_logger

_LOG = get_logger(__name__)


def _sanitize(name: str) -> str:
    """Return a Docker-safe name fragment."""
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
    return "".join(c if c in allowed else "_" for c in name)


class LinuxVM:
    """Manage a lightweight Docker-based VM.

    The default image provides Python and pip so packages can be installed
    immediately. A custom image can be supplied via ``VM_IMAGE``.
    """

    def __init__(
        self,
        username: str,
        *,
        config: Config = DEFAULT_CONFIG,
    ) -> None:
        self.config = config
        self._image = config.vm_image
        self._name = f"chat-vm-{_sanitize(username)}"
        self._running = False
        self._host_dir = Path(config.upload_dir) / username
        self._host_dir.mkdir(parents=True, exist_ok=True)
        self._state_dir = Path(config.vm_state_dir) / _sanitize(username)
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._notifications_dir = self._state_dir / "notifications"
        self._notifications_dir.mkdir(parents=True, exist_ok=True)
        self._env = {}
        if config.vm_docker_host:
            _LOG.debug("Using custom Docker host: %s", config.vm_docker_host)
            self._env["DOCKER_HOST"] = config.vm_docker_host

    @property
    def persist_vms(self) -> bool:
        return self.config.persist_vms

    def start(self) -> None:
        """Start the VM if it is not already running."""
        if self._running:
            return

        try:
            inspect = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}}", self._name],
                capture_output=True,
                text=True,
                env=self._env if self._env else None,
            )
            if inspect.returncode == 0:
                if inspect.stdout.strip() == "true":
                    self._running = True
                    return
                subprocess.run(
                    ["docker", "start", self._name],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=self._env if self._env else None,
                )
                self._running = True
                return

            subprocess.run(
                ["docker", "pull", self._image],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=self._env if self._env else None,
            )
            subprocess.run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--name",
                    self._name,
                    "-v",
                    f"{self._host_dir}:/data",
                    "-v",
                    f"{self._state_dir}:/state",
                    self._image,
                    "sleep",
                    "infinity",
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=self._env if self._env else None,
            )
            self._running = True
        except Exception as exc:  # pragma: no cover - runtime failures
            _LOG.error("Failed to start VM: %s", exc)
            raise RuntimeError(f"Failed to start VM: {exc}") from exc

    def execute(
        self,
        command: str,
        *,
        timeout: int | None = 3,
        detach: bool = False,
        stdin_data: str | bytes | None = None,
    ) -> str:
        """Execute a command inside the running VM.

        Parameters
        ----------
        command:
            The shell command to run inside the container.
        timeout:
            Maximum time in seconds to wait for completion. Set to ``None``
            to wait indefinitely. Ignored when ``detach`` is ``True``.
        detach:
            Run the command in the background without waiting for it to finish.
        """
        if not self._running:
            raise RuntimeError("VM is not running")

        cmd = [
            "docker",
            "exec",
            "-i",
        ]
        if detach:
            cmd.append("-d")
        cmd.extend(
            [
                self._name,
                "bash",
                "-lc",
                command,
            ]
        )

        try:
            completed = subprocess.run(
                cmd,
                input=stdin_data,
                capture_output=True,
                text=isinstance(stdin_data, str),
                timeout=self.config.hard_timeout,
                env=self._env if self._env else None,
            )
        except subprocess.TimeoutExpired as exc:
            return f"Command timed out after {timeout}s: {exc.cmd}"
        except Exception as exc:  # pragma: no cover - unforeseen errors
            return f"Failed to execute command: {exc}"

        output = completed.stdout
        if completed.stderr:
            output = f"{output}\n{completed.stderr}" if output else completed.stderr
        return limit_chars(output)

    async def execute_async(
        self,
        command: str,
        *,
        timeout: int | None = 3,
        detach: bool = False,
        stdin_data: str | bytes | None = None,
    ) -> str:
        """Asynchronously execute ``command`` inside the running VM."""
        loop = asyncio.get_running_loop()
        func = partial(
            self.execute,
            command,
            timeout=self.config.hard_timeout,
            detach=detach,
            stdin_data=stdin_data,
        )
        return await loop.run_in_executor(None, func)

    def post_notification(self, message: str) -> None:
        """Store ``message`` in the VM's notification queue."""
        ts = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        path = self._notifications_dir / f"{ts}.txt"
        try:
            path.write_text(message)
        except Exception as exc:  # pragma: no cover - runtime errors
            _LOG.error("Failed to write notification: %s", exc)

    def fetch_notifications(self) -> list[str]:
        """Retrieve and clear queued notifications."""
        notes: list[str] = []
        for p in sorted(self._notifications_dir.glob("*.txt")):
            try:
                notes.append(p.read_text())
            except Exception as exc:  # pragma: no cover - runtime errors
                _LOG.error("Failed to read notification %s: %s", p, exc)
                continue
            try:
                p.unlink()
            except Exception as exc:  # pragma: no cover - runtime errors
                _LOG.warning("Failed to delete notification %s: %s", p, exc)
        return notes

    def stop(self) -> None:
        """Terminate the VM if running."""
        if not self._running:
            return

        if self.config.persist_vms:
            subprocess.run(
                ["docker", "stop", self._name],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=self._env if self._env else None,
            )
        else:
            subprocess.run(
                ["docker", "rm", "-f", self._name],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=self._env if self._env else None,
            )
        self._running = False

    def __enter__(self) -> "LinuxVM":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()


class VMRegistry:
    """Manage Linux VM instances on a per-user basis."""

    _vms: dict[str, LinuxVM] = {}
    _counts: dict[str, int] = {}
    _lock = Lock()

    @classmethod
    def acquire(cls, username: str, *, config: Config = DEFAULT_CONFIG) -> LinuxVM:
        """Return a running VM for ``username`` using ``config``."""

        with cls._lock:
            vm = cls._vms.get(username)
            if vm is None:
                vm = LinuxVM(username, config=config)
                cls._vms[username] = vm
                cls._counts[username] = 0
            cls._counts[username] += 1

        vm.start()
        return vm

    @classmethod
    def release(cls, username: str) -> None:
        """Release one reference to ``username``'s VM and stop it if unused."""

        with cls._lock:
            vm = cls._vms.get(username)
            if vm is None:
                return

            cls._counts[username] -= 1
            if cls._counts[username] <= 0:
                cls._counts[username] = 0
                if not vm.config.persist_vms:
                    vm.stop()
                del cls._vms[username]
                del cls._counts[username]

    @classmethod
    def shutdown_all(cls) -> None:
        """Stop and remove all managed VMs."""

        with cls._lock:
            for vm in cls._vms.values():
                if not vm.config.persist_vms:
                    vm.stop()
            cls._vms.clear()
            cls._counts.clear()

from ..utils.debug import debug_all
debug_all(globals())

