from __future__ import annotations

from typing import AsyncIterator, Iterable, Callable, Awaitable
from pathlib import Path
import base64
import json
import shlex
import shutil

from .config import Config, DEFAULT_CONFIG
from .vm import VMRegistry, LinuxVM
from .db import (
    add_document,
    list_sessions as _db_list_sessions,
    list_sessions_info as _db_list_sessions_info,
    list_documents as _db_list_documents,
    reset_memory as _db_reset_memory,
)
from .utils.memory import get_memory as _get_memory, set_memory as _set_memory
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
    "vm_send_input",
    "vm_send_keys",
    "send_notification",
    "list_sessions",
    "list_sessions_info",
    "list_documents",
    "get_memory",
    "set_memory",
    "reset_memory",
    "restart_terminal",
]

_LOG = get_logger(__name__)


async def _copy_to_vm_and_verify_async(
    vm: LinuxVM, local_path: Path, dest_path: str
) -> None:
    """Copy ``local_path`` into ``vm`` and verify it exists at ``dest_path``."""

    vm.copy_to_vm(local_path, dest_path)
    check_cmd = f"test -f {shlex.quote(dest_path)} && echo OK"
    result = await vm.execute_async(check_cmd)
    if "OK" not in result:
        raise RuntimeError(f"Failed to verify {dest_path} in VM")


def _copy_to_vm_and_verify(vm: LinuxVM, local_path: Path, dest_path: str) -> None:
    """Synchronous helper for :func:`_copy_to_vm_and_verify_async`."""

    vm.copy_to_vm(local_path, dest_path)
    check_cmd = f"test -f {shlex.quote(dest_path)} && echo OK"
    result = vm.execute(check_cmd)
    if "OK" not in result:
        raise RuntimeError(f"Failed to verify {dest_path} in VM")


async def team_chat(
    prompt: str,
    *,
    user: str = "default",
    session: str = "default",
    think: bool = True,
    config: Config | None = None,
    extra: dict[str, str] | None = None,
) -> AsyncIterator[str]:
    from .sessions.team import TeamChatSession

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
    """Upload ``file_path`` for access inside the VM."""

    cfg = config or DEFAULT_CONFIG
    src = Path(file_path)
    if not src.exists():
        raise FileNotFoundError(file_path)

    dest = Path(cfg.upload_dir) / user
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / src.name
    shutil.copy(src, target)

    vm = VMRegistry.acquire(user, session, config=cfg)
    try:
        await _copy_to_vm_and_verify_async(vm, target, f"/data/{src.name}")
    finally:
        VMRegistry.release(user, session)

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

    vm = VMRegistry.acquire(user, session, config=cfg)
    try:
        await _copy_to_vm_and_verify_async(vm, target, f"/data/{filename}")
    finally:
        VMRegistry.release(user, session)

    add_document(user, str(target), filename)
    return f"/data/{filename}"


async def vm_execute(
    command: str,
    *,
    user: str = "default",
    session: str = "default",
    timeout: int | None = None,
    config: Config | None = None,
) -> str:
    """Execute ``command`` inside ``user``'s VM and return the output."""

    cfg = config or DEFAULT_CONFIG
    vm = VMRegistry.acquire(user, session, config=cfg)
    try:
        return await vm.execute_async(command, timeout=timeout)
    finally:
        VMRegistry.release(user, session)


async def vm_execute_stream(
    command: str,
    *,
    user: str = "default",
    session: str = "default",
    config: Config | None = None,
    input_responder: Callable[[str], Awaitable[str | None]] | None = None,
    raw: bool = True,
) -> AsyncIterator[str]:
    """Yield incremental output from ``command`` executed in ``user``'s VM."""

    cfg = config or DEFAULT_CONFIG
    vm = VMRegistry.acquire(user, session, config=cfg)
    try:
        async for part in vm.shell_execute_stream(
            command, input_responder=input_responder, raw=raw
        ):
            yield part
    finally:
        VMRegistry.release(user, session)


async def vm_send_input(
    data: str | bytes,
    *,
    user: str = "default",
    session: str = "default",
    config: Config | None = None,
) -> None:
    """Forward ``data`` to the user's running VM shell."""

    cfg = config or DEFAULT_CONFIG
    vm = VMRegistry.acquire(user, session, config=cfg)
    try:
        await vm.shell_send_input(data)
    finally:
        VMRegistry.release(user, session)


async def vm_send_keys(
    data: str,
    *,
    user: str = "default",
    session: str = "default",
    config: Config | None = None,
    delay: float = 0.05,
) -> None:
    """Simulate typing ``data`` into the user's VM shell."""

    cfg = config or DEFAULT_CONFIG
    vm = VMRegistry.acquire(user, session, config=cfg)
    try:
        await vm.shell_send_keys(data, delay=delay)
    finally:
        VMRegistry.release(user, session)


async def list_dir(
    path: str,
    *,
    user: str = "default",
    session: str = "default",
    config: Config | None = None,
) -> Iterable[tuple[str, bool]]:
    """Return ``(name, is_dir)`` tuples for ``path`` inside the VM."""

    output = await vm_execute(
        f"ls -1ap {shlex.quote(path)}", user=user, session=session, config=config
    )
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
    session: str = "default",
    config: Config | None = None,
) -> str:
    """Return the contents of ``path`` from the VM."""

    return await vm_execute(
        f"cat {shlex.quote(path)}", user=user, session=session, config=config
    )


async def write_file(
    path: str,
    content: str,
    *,
    user: str = "default",
    session: str = "default",
    config: Config | None = None,
) -> str:
    """Write ``content`` to ``path`` inside the VM."""

    encoded = base64.b64encode(content.encode()).decode()
    cmd = (
        "python -c 'import base64,os; "
        f'open({json.dumps(path)}, "wb").write(base64.b64decode({json.dumps(encoded)}))\''
    )
    await vm_execute(cmd, user=user, session=session, config=config)
    return "Saved"


async def delete_path(
    path: str,
    *,
    user: str = "default",
    session: str = "default",
    config: Config | None = None,
) -> str:
    """Delete a file or directory at ``path`` inside the VM."""

    cmd = (
        f"bash -c 'if [ -d {shlex.quote(path)} ]; then rm -rf {shlex.quote(path)} && echo Deleted; "
        f"elif [ -e {shlex.quote(path)} ]; then rm -f {shlex.quote(path)} && echo Deleted; "
        f"else echo File not found; fi'"
    )
    return await vm_execute(cmd, user=user, session=session, config=config)


async def download_file(
    path: str,
    *,
    user: str = "default",
    dest: str | None = None,
    session: str = "default",
    config: Config | None = None,
) -> str:
    """Copy ``path`` from the VM to ``dest`` and return the destination."""

    cfg = config or DEFAULT_CONFIG
    vm = VMRegistry.acquire(user, session, config=cfg)
    try:
        target_dir = Path(dest or cfg.return_dir) / user
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / Path(path).name
        vm.copy_from_vm(path, target)
        return str(target)
    finally:
        VMRegistry.release(user, session)


def send_notification(
    message: str,
    *,
    user: str = "default",
    session: str = "default",
    config: Config | None = None,
) -> None:
    """Post ``message`` to ``user``'s notification queue."""

    cfg = config or DEFAULT_CONFIG
    vm = VMRegistry.acquire(user, session, config=cfg)
    try:
        vm.post_notification(str(message))
    finally:
        VMRegistry.release(user, session)


async def list_sessions(user: str = "default") -> list[str]:
    """Return all session names for ``user``."""

    return _db_list_sessions(user)


async def list_sessions_info(user: str = "default") -> list[dict[str, str]]:
    """Return session names with last message snippet."""

    return _db_list_sessions_info(user)


async def list_documents(user: str = "default") -> list[dict[str, str]]:
    """Return info about uploaded documents."""

    return _db_list_documents(user)


async def get_memory(user: str = "default") -> str:
    """Return persistent memory for ``user``."""

    return _get_memory(user)


async def set_memory(user: str = "default", memory: str = "") -> str:
    """Persist new ``memory`` for ``user`` and return it."""

    return _set_memory(user, memory)


async def reset_memory(user: str = "default") -> str:
    """Reset ``user`` memory to default and return the value."""

    return _db_reset_memory(user)


async def restart_terminal(
    *, user: str = "default", session: str = "default", config: Config | None = None
) -> str:
    """Restart ``user``'s VM and clear the persistent shell."""

    cfg = config or DEFAULT_CONFIG
    vm = VMRegistry.acquire(user, session, config=cfg)
    try:
        vm.restart()
    finally:
        VMRegistry.release(user, session)
    return "restarted"
