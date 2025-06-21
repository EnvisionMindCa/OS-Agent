# -*- coding: utf-8 -*-
"""Asynchronous watcher for VM returned files."""

from __future__ import annotations

import asyncio
import shutil
from contextlib import suppress
from pathlib import Path
from typing import Awaitable, Callable

from ..utils.logging import get_logger

__all__ = ["ReturnWatcher"]

_LOG = get_logger(__name__)


class ReturnWatcher:
    """Watch the VM's return directory and forward files."""

    def __init__(
        self,
        queue_dir: Path,
        dest_dir: Path,
        callback: Callable[[str, bytes], Awaitable[None]],
        *,
        interval: int = 5,
    ) -> None:
        self._queue_dir = queue_dir
        self._dest_dir = dest_dir
        self._callback = callback
        self._interval = interval
        self._task: asyncio.Task | None = None
        self._use_watchfiles = False

    async def start(self) -> None:
        """Begin monitoring the return directory."""
        if self._task is not None:
            return
        try:
            from watchfiles import awatch  # type: ignore
            self._watch_impl = self._watch_watchfiles
            self._use_watchfiles = True
            _LOG.debug("Using watchfiles for return directory monitoring")
        except Exception:  # pragma: no cover - optional dependency
            self._watch_impl = self._watch_polling
            _LOG.debug(
                "watchfiles not available, falling back to polling every %ss",
                self._interval,
            )
        self._task = asyncio.create_task(self._watch_impl())

    async def stop(self) -> None:
        """Stop monitoring the return directory."""
        if self._task and not self._task.done():
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
        self._task = None

    # ------------------------------------------------------------------
    async def _watch_watchfiles(self) -> None:
        from watchfiles import awatch  # type: ignore

        try:
            async for _ in awatch(self._queue_dir):
                await self._process_queue()
        except asyncio.CancelledError:  # pragma: no cover - lifecycle
            pass

    async def _watch_polling(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._interval)
                await self._process_queue()
        except asyncio.CancelledError:  # pragma: no cover - lifecycle
            pass

    async def _process_queue(self) -> None:
        for p in sorted(self._queue_dir.glob("*")):
            if not p.is_file():
                continue
            dest = self._dest_dir / p.name
            try:
                shutil.move(str(p), dest)
                data = dest.read_bytes()
                dest.unlink()
            except Exception as exc:  # pragma: no cover - runtime errors
                _LOG.error("Failed to process returned file %s: %s", p, exc)
                continue
            await self._safe_callback(dest.name, data)

    async def _safe_callback(self, name: str, data: bytes) -> None:
        try:
            await self._callback(name, data)
        except Exception as exc:  # pragma: no cover - runtime errors
            _LOG.error("ReturnWatcher callback failed for %s: %s", name, exc)

    async def __aenter__(self) -> "ReturnWatcher":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.stop()
