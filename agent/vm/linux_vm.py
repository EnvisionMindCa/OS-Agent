from __future__ import annotations

import subprocess
import time
import asyncio
from typing import AsyncIterator, Callable, Awaitable
import shutil
import datetime
from functools import partial
from pathlib import Path

from ..utils.debug import debug_all
from .shell import PersistentShell

from ..config import (
    DEFAULT_CONFIG,
    Config,
)
from ..utils.helpers import limit_chars
from ..utils import PTYProcess

from ..utils.logging import get_logger

_LOG = get_logger(__name__)


def _sanitize(name: str) -> str:
    """Return a Docker-safe name fragment."""
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
    return "".join(c if c in allowed else "_" for c in name)


class LinuxVM:
    """Manage a lightweight Docker-based VM.

    The default image is ``python:3.11-slim``—a minimal Debian environment
    where packages can be installed via ``apt``. A custom image can be supplied
    via ``VM_IMAGE`` and the container name is derived from
    ``VM_CONTAINER_TEMPLATE``.
    """

    def __init__(
        self,
        username: str,
        *,
        config: Config = DEFAULT_CONFIG,
    ) -> None:
        self.config = config
        self._image = config.vm_image
        self._name = config.vm_container_template.format(user=_sanitize(username))
        self._running = False
        self._host_dir = (Path(config.upload_dir) / username).resolve()
        self._host_dir.mkdir(parents=True, exist_ok=True)
        self._state_dir = (Path(config.vm_state_dir) / _sanitize(username)).resolve()
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._notifications_dir = self._state_dir / "notifications"
        self._notifications_dir.mkdir(parents=True, exist_ok=True)
        self._return_queue_dir = self._state_dir / "return"
        self._return_queue_dir.mkdir(parents=True, exist_ok=True)
        self._return_dir = (Path(config.return_dir) / _sanitize(username)).resolve()
        self._return_dir.mkdir(parents=True, exist_ok=True)
        self._env = {}
        if config.vm_docker_host:
            _LOG.debug("Using custom Docker host: %s", config.vm_docker_host)
            self._env["DOCKER_HOST"] = config.vm_docker_host
        self._shell: PersistentShell | None = None

    @property
    def persist_vms(self) -> bool:
        return self.config.persist_vms

    @property
    def return_dir(self) -> Path:
        return self._return_dir

    @property
    def return_queue_dir(self) -> Path:
        """Directory backing the VM's ``/return`` queue."""
        return self._return_queue_dir

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
                    "-v",
                    f"{self._return_queue_dir}:/return",
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

    # ------------------------------------------------------------------
    def _ensure_shell(self) -> PersistentShell:
        if self._shell is None:
            self._shell = PersistentShell(self._name, self._env or None)
        return self._shell

    async def shell_execute(
        self,
        command: str,
        *,
        input_responder: Callable[[str], Awaitable[str | None]] | None = None,
    ) -> str:
        """Run ``command`` in a persistent shell session."""

        shell = self._ensure_shell()
        return await shell.execute(command, input_responder=input_responder)

    async def shell_execute_stream(
        self,
        command: str,
        *,
        input_responder: Callable[[str], Awaitable[str | None]] | None = None,
        raw: bool = False,
    ) -> AsyncIterator[str]:
        """Yield output from running ``command`` in the persistent shell."""

        shell = self._ensure_shell()
        async for part in shell.execute_stream(
            command, input_responder=input_responder, raw=raw
        ):
            yield part

    async def shell_send_input(self, data: str | bytes) -> None:
        """Forward ``data`` to the persistent shell's stdin."""

        shell = self._ensure_shell()
        await shell.send_input(data)

    async def shell_send_keys(self, data: str, *, delay: float = 0.05) -> None:
        """Simulate typing ``data`` in the persistent shell."""

        shell = self._ensure_shell()
        await shell.send_keys(data, delay=delay)

    def execute(
        self,
        command: str,
        *,
        timeout: int | None = None,
        detach: bool = False,
        stdin_data: str | bytes | None = None,
    ) -> str:
        """Execute a command inside the running VM.

        Parameters
        ----------
        command:
            The shell command to run inside the container.
        timeout:
            Maximum time in seconds to wait for completion. If ``None``,
            the VM's ``hard_timeout`` configuration is used. Set the
            configuration value to ``None`` for no timeout. Ignored when
            ``detach`` is ``True``.
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

        if detach:
            try:
                subprocess.run(
                    cmd,
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=self._env if self._env else None,
                )
            except Exception as exc:  # pragma: no cover - unforeseen errors
                return f"Failed to execute command: {exc}"
            return ""

        proc = PTYProcess(cmd, env=self._env if self._env else None)
        proc.spawn()
        if stdin_data:
            if isinstance(stdin_data, bytes):
                stdin_text = stdin_data.decode()
            else:
                stdin_text = stdin_data
            proc.send(stdin_text)

        output_parts: list[str] = []
        start = time.monotonic()
        limit = timeout if timeout is not None else self.config.hard_timeout
        while proc.is_alive():
            output_parts.append(proc.read())
            if limit is not None and time.monotonic() - start > limit:
                proc.terminate()
                return f"Command timed out after {limit}s: {' '.join(cmd)}"

        output_parts.append(proc.read())  # flush remaining output
        proc.terminate()
        output = "".join(output_parts)
        return limit_chars(output)

    async def execute_async(
        self,
        command: str,
        *,
        timeout: int | None = None,
        detach: bool = False,
        stdin_data: str | bytes | None = None,
    ) -> str:
        """Asynchronously execute ``command`` inside the running VM."""
        loop = asyncio.get_running_loop()
        func = partial(
            self.execute,
            command,
            timeout=timeout,
            detach=detach,
            stdin_data=stdin_data,
        )
        return await loop.run_in_executor(None, func)

    # ------------------------------------------------------------------
    def copy_to_vm(self, local_path: Path, dest_path: str) -> None:
        """Copy ``local_path`` from the host into the container at ``dest_path``."""

        self.start()
        try:
            subprocess.run(
                ["docker", "cp", str(local_path), f"{self._name}:{dest_path}"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=self._env if self._env else None,
            )
        except Exception as exc:  # pragma: no cover - runtime errors
            _LOG.error("Failed to copy %s to VM: %s", local_path, exc)
            raise RuntimeError(f"Failed to copy {local_path} to VM: {exc}") from exc

    def copy_from_vm(self, src_path: str, dest_path: Path) -> None:
        """Copy ``src_path`` from the container to ``dest_path`` on the host."""

        self.start()
        try:
            subprocess.run(
                ["docker", "cp", f"{self._name}:{src_path}", str(dest_path)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=self._env if self._env else None,
            )
        except Exception as exc:  # pragma: no cover - runtime errors
            _LOG.error("Failed to copy %s from VM: %s", src_path, exc)
            raise RuntimeError(f"Failed to copy {src_path} from VM: {exc}") from exc

    def fetch_returned_files(self) -> list[tuple[str, bytes]]:
        """Return queued files and remove them from the VM.

        Files are first moved to ``self._return_dir`` so other helpers can
        access the same path if needed. After reading the contents each file
        is deleted from the host to keep the directory clean.
        """

        files: list[tuple[str, bytes]] = []
        for p in sorted(self._return_queue_dir.glob("*")):
            if not p.is_file():
                continue
            dest = self._return_dir / p.name
            try:
                shutil.move(str(p), dest)
                data = dest.read_bytes()
                dest.unlink()
                files.append((p.name, data))
            except Exception as exc:  # pragma: no cover - runtime errors
                _LOG.error("Failed to process returned file %s: %s", p, exc)
        return files

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

        if self._shell is not None:
            try:
                asyncio.run(self._shell.stop())
            except RuntimeError:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(self._shell.stop())
                loop.close()
            self._shell = None

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

    def restart(self) -> None:
        """Restart the container and clear the persistent shell."""
        self.stop()
        self.start()

    def __enter__(self) -> "LinuxVM":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()



__all__ = ["LinuxVM"]

debug_all(globals())

