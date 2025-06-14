from __future__ import annotations

import subprocess
import asyncio
from functools import partial
from pathlib import Path
import re
import io
import shutil

from threading import Lock

from ..config import UPLOAD_DIR, VM_IMAGE, PERSIST_VMS, VM_STATE_DIR, VM_CMD
from ..utils.helpers import limit_chars
import pexpect

from ..utils.logging import get_logger

_LOG = get_logger(__name__)


def is_vm_available() -> bool:
    """Return ``True`` if the container runtime executable is available."""
    if shutil.which(VM_CMD) is None:
        return False
    try:
        subprocess.run(
            [VM_CMD, "info"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except Exception:
        return False
    return True


def _sanitize(name: str) -> str:
    """Return a runtime-safe name fragment."""
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.")
    return "".join(c if c in allowed else "_" for c in name)


class ContainerVM:
    """Manage a lightweight Podman-based VM.

    The default image provides Python and pip so packages can be installed
    immediately. A custom image can be supplied via ``VM_IMAGE``.
    """

    def __init__(
        self,
        username: str,
        image: str = VM_IMAGE,
        host_dir: str = UPLOAD_DIR,
    ) -> None:
        self._image = image
        self._name = f"chat-vm-{_sanitize(username)}"
        self._running = False
        self._host_dir = Path(host_dir)
        self._host_dir.mkdir(parents=True, exist_ok=True)
        self._state_dir = Path(VM_STATE_DIR) / _sanitize(username)
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._hostname = None
        self._user = None
        self._prompt_env = None
        self._prompt_re = None

    def _fetch_username(self) -> str:
        """Return the username inside the running container."""
        try:
            result = subprocess.run(
                [VM_CMD, "exec", self._name, "id", "-un"],
                capture_output=True,
                text=True,
                check=False,
            )
            user = result.stdout.strip()
            return user or "root"
        except Exception as exc:  # pragma: no cover - runtime failures
            _LOG.error("Failed to get container username: %s", exc)
            return "root"

    def _update_prompt(self) -> None:
        """Update prompt patterns based on current user and host."""
        if not self._user or not self._hostname:
            return
        suffix = "#" if self._user == "root" else "$"
        prefix = f"{self._user}@{self._hostname}:"
        self._prompt_env = f"{prefix}" + r"\w" + f"{suffix} "
        self._prompt_re = re.compile(
            re.escape(prefix) + r"[^\r\n]*" + re.escape(f"{suffix} ")
        )

    def start(self) -> None:
        """Start the VM if it is not already running."""
        if self._running:
            return

        try:
            inspect = subprocess.run(
                [VM_CMD, "inspect", "-f", "{{.State.Running}}", self._name],
                capture_output=True,
                text=True,
            )
            if inspect.returncode == 0:
                if inspect.stdout.strip() == "true":
                    self._running = True
                else:
                    subprocess.run(
                        [VM_CMD, "start", self._name],
                        check=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    self._running = True
                result = subprocess.run(
                    [VM_CMD, "exec", self._name, "hostname"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self._hostname = result.stdout.strip() or self._name
                self._user = self._fetch_username()
                self._update_prompt()
                return

            subprocess.run(
                [VM_CMD, "pull", self._image],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            subprocess.run(
                [
                    VM_CMD,
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
            )
            self._running = True
            result = subprocess.run(
                [VM_CMD, "exec", self._name, "hostname"],
                capture_output=True,
                text=True,
                check=False,
            )
            self._hostname = result.stdout.strip() or self._name
            self._user = self._fetch_username()
            self._update_prompt()
        except Exception as exc:  # pragma: no cover - runtime failures
            _LOG.error("Failed to start VM: %s", exc)
            raise RuntimeError(f"Failed to start VM: {exc}") from exc

    def execute(
        self,
        command: str,
        *,
        timeout: int | None = 3,
        stdin_data: str | bytes | None = None,
    ) -> str:
        """Execute ``command`` inside the VM and return a full terminal transcript."""

        if not self._running:
            raise RuntimeError("VM is not running")

        prompt_env = self._prompt_env or ""
        prompt_re = self._prompt_re or ""
        child = pexpect.spawn(
            VM_CMD,
            [
                "exec",
                "-i",
                "-t",
                self._name,
                "bash",
                "--noprofile",
                "--norc",
                "-i",
            ],
            env={"PS1": prompt_env},
            encoding="utf-8",
            echo=True,
        )
        transcript = io.StringIO()
        child.logfile_read = transcript

        try:
            child.expect(prompt_re)
        except Exception:
            child.close(force=True)
            return "Failed to start shell"

        child.sendline(command)
        if stdin_data is not None:
            child.send(stdin_data)

        try:
            child.expect(prompt_re, timeout=None if timeout is None else timeout)
        except pexpect.TIMEOUT:
            pass

        child.close(force=True)
        return limit_chars(transcript.getvalue())

    async def execute_async(
        self,
        command: str,
        *,
        timeout: int | None = 3,
        stdin_data: str | bytes | None = None,
    ) -> str:
        """Asynchronously execute ``command`` inside the running VM."""
        loop = asyncio.get_running_loop()
        func = partial(
            self.execute,
            command,
            timeout=timeout,
            stdin_data=stdin_data,
        )
        return await loop.run_in_executor(None, func)

    def stop(self) -> None:
        """Terminate the VM if running."""
        if not self._running:
            return

        if PERSIST_VMS:
            subprocess.run(
                [VM_CMD, "stop", self._name],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        else:
            subprocess.run(
                [VM_CMD, "rm", "-f", self._name],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        self._running = False

    def __enter__(self) -> "ContainerVM":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()


class VMRegistry:
    """Manage Linux VM instances on a per-user basis."""

    _vms: dict[str, ContainerVM] = {}
    _counts: dict[str, int] = {}
    _lock = Lock()

    @classmethod
    def acquire(cls, username: str) -> ContainerVM:
        """Return a running VM for ``username``, creating it if needed."""

        with cls._lock:
            vm = cls._vms.get(username)
            if vm is None:
                vm = ContainerVM(
                    username,
                    host_dir=str(Path(UPLOAD_DIR) / username),
                )
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
                if not PERSIST_VMS:
                    vm.stop()
                del cls._vms[username]
                del cls._counts[username]

    @classmethod
    def shutdown_all(cls) -> None:
        """Stop and remove all managed VMs."""

        with cls._lock:
            if not PERSIST_VMS:
                for vm in cls._vms.values():
                    vm.stop()
            cls._vms.clear()
            cls._counts.clear()

# Backwards compatibility
LinuxVM = ContainerVM
