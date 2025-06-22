from __future__ import annotations

import asyncio
import uuid
from contextlib import suppress
from typing import AsyncIterator, Callable, Awaitable, Optional
import json

from ..utils.logging import get_logger


class PersistentShell:
    """Maintain a persistent bash session inside a running container."""

    def __init__(self, container_name: str, env: dict[str, str] | None = None) -> None:
        self._container = container_name
        self._env = env
        self._proc: asyncio.subprocess.Process | None = None
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._reader: asyncio.Task | None = None
        self._log = get_logger(__name__)

    async def start(self) -> None:
        if self._proc:
            return
        # ``script`` ensures the underlying shell has a pseudo TTY so
        # interactive prompts appear in the captured output. ``-f`` forces
        # flushing so output is streamed immediately. ``docker`` would normally
        # suppress prompts when stdout is piped.
        self._proc = await asyncio.create_subprocess_exec(
            "docker",
            "exec",
            "-i",
            self._container,
            "script",
            "-q",
            "-f",
            "-c",
            "bash -i",
            "/dev/null",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=self._env,
        )
        self._reader = asyncio.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        assert self._proc and self._proc.stdout
        buf = ""
        while True:
            chunk = await self._proc.stdout.read(1)
            if not chunk:
                if buf:
                    await self._queue.put(buf)
                break
            char = chunk.decode()
            if char == "\b":
                buf = buf[:-1]
                continue
            buf += char
            if self._is_input_prompt(buf):
                await self._queue.put(buf)
                buf = ""
            elif char in {"\n", "\r"}:
                await self._queue.put(buf)
                buf = ""

    async def stop(self) -> None:
        if self._reader and not self._reader.done():
            self._reader.cancel()
            with suppress(asyncio.CancelledError):
                await self._reader
        if self._proc and self._proc.returncode is None:
            self._proc.terminate()
            with suppress(Exception):
                await self._proc.wait()
        self._proc = None
        self._reader = None

    async def execute(
        self,
        command: str,
        *,
        input_responder: Optional[Callable[[str], Awaitable[str | None]]] = None,
    ) -> str:
        """Run ``command`` in the persistent shell and return the output."""

        result: list[str] = []
        async for part in self.execute_stream(
            command, input_responder=input_responder
        ):
            result.append(part)
        return "".join(result)

    @staticmethod
    def _is_input_prompt(text: str) -> bool:
        stripped = text.rstrip()
        if not stripped:
            return False
        s = stripped.lower()
        if "(y/n)" in s or "[y/n]" in s or s.endswith("yes/no?"):
            return True
        if s.endswith("?"):
            return True
        if s.endswith(">"):
            return True
        if "password:" in s and s.rstrip().endswith(":"):
            return True
        if s.rstrip().endswith(":"):
            if "//" in s:
                return False
            return True
        if s.rstrip().endswith(">") and "enter" in s:
            return True
        return False

    async def _default_input_responder(self, prompt: str) -> str | None:
        """Return a basic response for common CLI prompts."""

        s = prompt.strip().lower()
        if not s:
            return None
        if "[y/n]" in s or "(y/n)" in s or s.endswith("yes/no?"):
            return "y"
        if "press enter" in s or "press return" in s or "any key" in s:
            return ""
        if "default" in s and ("enter" in s or "return" in s):
            return ""
        return None

    async def execute_stream(
        self,
        command: str,
        *,
        input_responder: Optional[Callable[[str], Awaitable[str | None]]] = None,
    ) -> AsyncIterator[str]:
        """Yield command output incrementally as it is produced."""
        await self.start()
        assert self._proc and self._proc.stdin
        sentinel = f"__CMD_DONE_{uuid.uuid4().hex}__"
        self._proc.stdin.write(f"{command}\necho {sentinel}\n".encode())
        await self._proc.stdin.drain()
        while True:
            line = await self._queue.get()
            if sentinel in line:
                break
            if self._is_input_prompt(line):
                yield line
                handler = input_responder or self._default_input_responder
                if handler is not None:
                    try:
                        reply = await handler(line.strip())
                    except Exception as exc:  # pragma: no cover - unforeseen errors
                        self._log.error("Prompt responder failed: %s", exc)
                        reply = None
                    if reply is not None:
                        await self.send_input(
                            reply if reply.endswith("\n") else f"{reply}\n"
                        )
                        continue
                yield json.dumps({"stdin_request": line.strip()})
            else:
                yield line

    async def send_input(self, data: str | bytes) -> None:
        """Forward ``data`` to the running shell's standard input."""

        await self.start()
        assert self._proc and self._proc.stdin
        if isinstance(data, str):
            data = data.encode()
        self._proc.stdin.write(data)
        await self._proc.stdin.drain()
