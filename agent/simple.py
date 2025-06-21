from __future__ import annotations

from typing import AsyncIterator, Iterable
from pathlib import Path
import base64
import json
import shlex

import shutil

from .sessions.team import TeamChatSession
from .config import Config, DEFAULT_CONFIG
from .vm import VMRegistry
from .db import add_document
from .utils.logging import get_logger

__all__ = [
    "team_chat",
    "upload_document",
    "upload_data",
    "list_dir",
    "read_file",
    "write_file",
    "delete_path",
    "download_file",
    "vm_execute",
    "vm_execute_stream",
    "send_notification",
]


_LOG = get_logger(__name__)


async def team_chat(
    prompt: str,
    *,
    user: str = "default",
    session: str = "default",
    think: bool = True,
    config: Config | None = None,
    extra: dict[str, str] | None = None,
) -> AsyncIterator[str]:
    async with TeamChatSession(
        user=user,
        session=session,
        think=think,
        config=config,
    ) as chat:
        async for part in chat.chat_stream(prompt, extra=extra):
            yield part


async def upload_document(
    file_path: str,
    *,
    user: str = "default",
    session: str = "default",
    config: Config | None = None,
) -> str:
    """Upload ``file_path`` for access inside the VM.

    The file becomes available under ``/data`` in the VM.
    """
    cfg = config or DEFAULT_CONFIG
    src = Path(file_path)
    if not src.exists():
        raise FileNotFoundError(file_path)

    dest = Path(cfg.upload_dir) / user
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / src.name
    shutil.copy(src, target)

    vm = VMRegistry.acquire(user, config=cfg)
    try:
        try:
            vm.copy_to_vm(target, f"/data/{src.name}")
        except Exception as exc:  # pragma: no cover - runtime errors
            _LOG.warning("Failed to copy document into VM: %s", exc)
    finally:
        VMRegistry.release(user)

    add_document(user, str(target), src.name)
    return f"/data/{src.name}"


async def upload_data(
    data: bytes,
    filename: str,
    *,
    user: str = "default",
    session: str = "default",
    config: Config | None = None,
) -> str:
    """Upload raw ``data`` as ``filename`` for access inside the VM."""

    cfg = config or DEFAULT_CONFIG
    dest = Path(cfg.upload_dir) / user
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / filename
    target.write_bytes(data)

    vm = VMRegistry.acquire(user, config=cfg)
    try:
        try:
            vm.copy_to_vm(target, f"/data/{filename}")
        except Exception as exc:  # pragma: no cover - runtime errors
            _LOG.warning("Failed to copy document into VM: %s", exc)
    finally:
        VMRegistry.release(user)

    add_document(user, str(target), filename)
    return f"/data/{filename}"


async def vm_execute(
    command: str,
    *,
    user: str = "default",
    timeout: int | None = None,
    config: Config | None = None,
) -> str:
    """Execute ``command`` inside ``user``'s VM and return the output."""
    cfg = config or DEFAULT_CONFIG
    vm = VMRegistry.acquire(user, config=cfg)
    try:
        return await vm.execute_async(command, timeout=timeout)
    finally:
        VMRegistry.release(user)


async def vm_execute_stream(
    command: str,
    *,
    user: str = "default",
    config: Config | None = None,
) -> AsyncIterator[str]:
    """Yield incremental output from ``command`` executed in ``user``'s VM."""

    cfg = config or DEFAULT_CONFIG
    vm = VMRegistry.acquire(user, config=cfg)
    try:
        async for part in vm.shell_execute_stream(command):
            yield part
    finally:
        VMRegistry.release(user)


async def list_dir(
    path: str,
    *,
    user: str = "default",
    config: Config | None = None,
) -> Iterable[tuple[str, bool]]:
    """Return an iterable of ``(name, is_dir)`` for ``path`` inside the VM."""
    output = await vm_execute(f"ls -1ap {shlex.quote(path)}", user=user, config=config)
    if output.startswith("ls:"):
        return []
    rows = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line in (".", ".."):
            continue
        is_dir = line.endswith("/")
        name = line[:-1] if is_dir else line
        rows.append((name, is_dir))
    return rows


async def read_file(
    path: str,
    *,
    user: str = "default",
    config: Config | None = None,
) -> str:
    """Return the contents of ``path`` from the VM."""
    return await vm_execute(f"cat {shlex.quote(path)}", user=user, config=config)


async def write_file(
    path: str,
    content: str,
    *,
    user: str = "default",
    config: Config | None = None,
) -> str:
    """Write ``content`` to ``path`` inside the VM."""
    encoded = base64.b64encode(content.encode()).decode()
    cmd = (
        "python -c 'import base64,os; "
        f'open({json.dumps(path)}, "wb").write(base64.b64decode({json.dumps(encoded)}))\''
    )
    await vm_execute(cmd, user=user, config=config)
    return "Saved"


async def delete_path(
    path: str,
    *,
    user: str = "default",
    config: Config | None = None,
) -> str:
    """Delete a file or directory at ``path`` inside the VM."""
    cmd = (
        f"bash -c 'if [ -d {shlex.quote(path)} ]; then rm -rf {shlex.quote(path)} && echo Deleted; "
        f"elif [ -e {shlex.quote(path)} ]; then rm -f {shlex.quote(path)} && echo Deleted; "
        f"else echo File not found; fi'"
    )
    return await vm_execute(cmd, user=user, config=config)


async def download_file(
    path: str,
    *,
    user: str = "default",
    dest: str | None = None,
    config: Config | None = None,
) -> str:
    """Copy ``path`` from the VM to ``dest`` and return the destination."""

    cfg = config or DEFAULT_CONFIG
    vm = VMRegistry.acquire(user, config=cfg)
    try:
        target_dir = Path(dest or cfg.return_dir) / user
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / Path(path).name
        vm.copy_from_vm(path, target)
        return str(target)
    finally:
        VMRegistry.release(user)


def send_notification(
    message: str,
    *,
    user: str = "default",
    config: Config | None = None,
) -> None:
    """Post ``message`` to ``user``'s notification queue."""

    cfg = config or DEFAULT_CONFIG
    vm = VMRegistry.acquire(user, config=cfg)
    try:
        vm.post_notification(str(message))
    finally:
        VMRegistry.release(user)


from .utils.debug import debug_all

debug_all(globals())
