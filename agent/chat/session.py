from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
import base64
from typing import AsyncIterator, List, Mapping

from ollama import AsyncClient, ChatResponse, Message

from ..config import (
    Config,
    DEFAULT_CONFIG,
)
from ..db import (
    Conversation,
    User,
    db,
    add_document,
    configure_db,
)
from ..utils.logging import get_logger
from .schema import Msg
from contextlib import suppress

from ..tools import execute_terminal_async, set_vm, create_memory_tool, _VM
from ..utils.memory import (
    get_memory,
    edit_memory as _edit_memory,
    edit_protected_memory as _edit_protected_memory,
)
from ..vm import VMRegistry
from ..api import _copy_to_vm_and_verify

from .state import SessionState, get_state
from .messages import (
    format_output,
    store_assistant_message,
    store_tool_message,
)

_LOG = get_logger(__name__)


class ChatSession:
    """Manage a conversation with persistent history and tool execution."""

    def __init__(
        self,
        user: str = "default",
        session: str = "default",
        host: str | None = None,
        model: str | None = None,
        *,
        system_prompt: str | None = None,
        tools: list[callable] | None = None,
        think: bool = True,
        persist: bool = True,
        config: Config | None = None,
    ) -> None:
        self._config = config or DEFAULT_CONFIG
        host = host or self._config.ollama_host
        model = model or self._config.model_name
        system_prompt = system_prompt or self._config.system_prompt

        # db.configure_db(self._config.db_path)
        db.init_db()
        self._client = AsyncClient(host=host)
        self._model = model
        self._user = db.get_or_create_user(user)
        self._persist = persist
        self._conversation = (
            db.get_or_create_conversation(self._user, session) if persist else None
        )
        self._vm = None
        self._base_system_prompt = system_prompt
        self._system_prompt = self._apply_memory(system_prompt)
        memory_tool = create_memory_tool(
            self._user.username, self._refresh_system_prompt
        )
        default_tool = execute_terminal_async
        self._tools = (tools or [default_tool]) + [memory_tool]
        self._tool_funcs = {func.__name__: func for func in self._tools}
        self._think = think
        self._current_tool_name: str | None = None
        self._messages: List[Msg] = self._load_history()
        self._state_data: SessionState = (
            get_state(self._conversation.id) if self._conversation else SessionState()
        )
        self._lock = self._state_data.lock
        self._prompt_queue: asyncio.Queue[
            tuple[str, dict[str, str] | None, asyncio.Queue[str | None]]
        ] = asyncio.Queue()
        self._worker: asyncio.Task | None = None
        self._notification_queue: asyncio.Queue[str] = asyncio.Queue()
        self._user_notification_queue: asyncio.Queue[str] = asyncio.Queue()
        self._notification_task: asyncio.Task | None = None
        self._return_watcher_task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    def _apply_memory(self, prompt: str) -> str:
        memory = get_memory(self._user.username)
        return f"{prompt}\n<memory>\n{memory}\n</memory>"

    def _refresh_system_prompt(self) -> None:
        self._system_prompt = self._apply_memory(self._base_system_prompt)

    def _append_extra(self, prompt: str, extra: dict[str, str] | None) -> str:
        if not extra:
            return prompt
        
        extra = {str(k): str(v) for k, v in extra.items() if v is not None}
        
        extra_str = json.dumps(extra, indent=2)
        return f"{prompt}\n<extra>\n{extra_str}\n</extra>"

    # ------------------------------------------------------------------
    # Properties exposing session state
    @property
    def _state(self) -> str:
        return self._state_data.status

    @_state.setter
    def _state(self, value: str) -> None:
        self._state_data.status = value

    @property
    def _tool_task(self) -> asyncio.Task | None:
        return self._state_data.tool_task

    @_tool_task.setter
    def _tool_task(self, task: asyncio.Task | None) -> None:
        self._state_data.tool_task = task


    @property
    def think(self) -> bool:
        """Default value for the ``think`` parameter in :meth:`ask`."""

        return self._think

    @think.setter
    def think(self, value: bool) -> None:
        self._think = value

    async def __aenter__(self) -> "ChatSession":
        self._vm = VMRegistry.acquire(self._user.username, config=self._config)
        set_vm(self._vm)
        self._notification_task = asyncio.create_task(self._monitor_notifications())
        self._return_watcher_task = asyncio.create_task(self._watch_return_dir())
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if _VM is self._vm:
            set_vm(None)
        if self._vm:
            VMRegistry.release(self._user.username)
        if self._notification_task and not self._notification_task.done():
            self._notification_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._notification_task
        if self._return_watcher_task and not self._return_watcher_task.done():
            self._return_watcher_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._return_watcher_task
        db.close()

    # ------------------------------------------------------------------
    def upload_document(self, file_path: str) -> str:
        """Save a document for later access inside the VM."""

        src = Path(file_path)
        if not src.exists():
            raise FileNotFoundError(file_path)

        dest = Path(self._config.upload_dir) / self._user.username
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / src.name
        shutil.copy(src, target)

        if self._vm is not None:
            _copy_to_vm_and_verify(self._vm, target, f"/data/{src.name}")

        add_document(self._user.username, str(target), src.name)
        return f"/data/{src.name}"

    def upload_data(self, data: bytes, filename: str) -> str:
        """Save ``data`` as ``filename`` for access inside the VM."""

        dest = Path(self._config.upload_dir) / self._user.username
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / filename
        target.write_bytes(data)

        if self._vm is not None:
            _copy_to_vm_and_verify(self._vm, target, f"/data/{filename}")

        add_document(self._user.username, str(target), filename)
        return f"/data/{filename}"

    # ------------------------------------------------------------------
    async def edit_memory(
        self,
        field: str,
        value: str | None = None,
        *,
        protected: bool = False,
    ) -> str:
        """Asynchronously edit the persistent memory for this session's user.

        The update runs in an executor so that blocking disk I/O does not
        stall the event loop.

        Parameters
        ----------
        field:
            Name of the memory entry to modify.
        value:
            New value for the field. If ``None``, the field is removed.
        protected:
            When ``True``, the field is stored under the ``protected_memory``
            section which is immutable from the agent's perspective.

        Returns
        -------
        str
            The updated memory as a JSON string.
        """

        loop = asyncio.get_running_loop()
        if protected:
            func = _edit_protected_memory
        else:
            func = _edit_memory
        memory = await loop.run_in_executor(
            None, lambda: func(self._user.username, field, value)
        )
        self._refresh_system_prompt()
        return memory

    # ------------------------------------------------------------------
    async def _queue_notification(self, message: str) -> None:
        """Queue ``message`` for delivery to the agent."""

        if self._vm is None:
            raise RuntimeError("Session is not active")

        self._vm.post_notification(str(message))
        await self._notification_queue.put(str(message))

    async def _send_notification(self, message: str) -> list[str]:
        """Queue ``message`` and return any immediate reply."""

        await self._queue_notification(message)
        replies: list[str] = []
        if (
            self._state == "idle"
            and self._prompt_queue.empty()
            and (not self._worker or self._worker.done())
        ):
            async for part in self._deliver_notifications():
                replies.append(part)
        return replies

    async def send_notification(self, message: str) -> None:
        """Queue a notification for this session's agent."""

        await self._queue_notification(message)
        if (
            self._state == "idle"
            and self._prompt_queue.empty()
            and (not self._worker or self._worker.done())
        ):
            async for _ in self._deliver_notifications():
                pass

    async def send_notification_with_reply(self, message: str) -> list[str]:
        """Queue ``message`` and return any immediate reply from the agent."""

        await self._queue_notification(message)
        replies: list[str] = []
        if (
            self._state == "idle"
            and self._prompt_queue.empty()
            and (not self._worker or self._worker.done())
        ):
            async for part in self._deliver_notifications():
                replies.append(part)
        return replies

    async def send_notification_stream(self, message: str) -> AsyncIterator[str]:
        """Queue ``message`` and yield any immediate reply from the agent."""

        await self._queue_notification(message)
        if (
            self._state == "idle"
            and self._prompt_queue.empty()
            and (not self._worker or self._worker.done())
        ):
            async for part in self._deliver_notifications():
                yield part

    # ------------------------------------------------------------------
    def _load_history(self) -> List[Msg]:
        messages: List[Msg] = []
        if not self._persist or not self._conversation:
            return messages
        for msg in db.list_messages(self._conversation):
            if msg.role == "system":
                continue
            if msg.role == "assistant":
                try:
                    data = json.loads(msg.content)
                except json.JSONDecodeError:
                    messages.append({"role": "assistant", "content": msg.content})
                else:
                    if isinstance(data, list):
                        messages.append(
                            {
                                "role": "assistant",
                                "tool_calls": [Message.ToolCall(**c) for c in data],
                            }
                        )
                    elif isinstance(data, dict):
                        msg_data: Msg = {"role": "assistant"}
                        if content := data.get("content"):
                            msg_data["content"] = content
                        if calls := data.get("tool_calls"):
                            msg_data["tool_calls"] = [
                                Message.ToolCall(**c) for c in calls
                            ]
                        messages.append(msg_data)
                    else:
                        messages.append({"role": "assistant", "content": str(data)})
            elif msg.role == "user":
                messages.append({"role": "user", "content": msg.content})
            else:
                try:
                    data = json.loads(msg.content)
                except json.JSONDecodeError:
                    messages.append({"role": "tool", "content": msg.content})
                else:
                    if isinstance(data, dict):
                        msg_data: Msg = {"role": "tool"}
                        if name := data.get("name"):
                            msg_data["name"] = name
                        msg_data["content"] = data.get("content", "")
                        messages.append(msg_data)
                    else:
                        messages.append({"role": "tool", "content": str(data)})
        return messages

    # ------------------------------------------------------------------
    async def ask(
        self, messages: List[Msg], *, think: bool | None = None
    ) -> ChatResponse:
        """Send a chat request, automatically prepending the system prompt."""

        if not messages or messages[0].get("role") != "system":
            payload = [{"role": "system", "content": self._system_prompt}, *messages]
        else:
            payload = messages

        if think is None:
            think = self._think

        return await self._client.chat(
            self._model,
            messages=payload,
            think=think,
            tools=self._tools,
            keep_alive=-1,
            options={"num_ctx": self._config.num_ctx, "temperature": 0},
        )

    async def _run_tool_async(self, func, **kwargs) -> str:
        if asyncio.iscoroutinefunction(func):
            return await func(**kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: func(**kwargs))

    # ------------------------------------------------------------------
    def _add_tool_message(
        self,
        conversation: Conversation,
        messages: list[Msg],
        name: str,
        content: str,
    ) -> None:
        messages.append({"role": "tool", "name": name, "content": content})
        if self._persist and conversation:
            store_tool_message(conversation, name, content)

    def _add_assistant_message(
        self,
        conversation: Conversation,
        messages: list[Msg],
        message: Message,
    ) -> None:
        if self._persist and conversation:
            store_assistant_message(conversation, message)
        messages.append(message.model_dump())

    async def _flush_notifications(self) -> bool:
        """Return ``True`` if any queued notifications were written."""

        delivered = False
        while not self._notification_queue.empty():
            note = await self._notification_queue.get()
            self._add_tool_message(
                self._conversation,
                self._messages,
                "notification",
                note,
            )
            delivered = True
        return delivered

    async def _deliver_notifications(self) -> AsyncIterator[str]:
        """Yield assistant replies for any queued notifications."""

        async for part in self._deliver_notifications_stream():
            yield part

    async def _deliver_notifications_stream(self) -> AsyncIterator[str]:
        """Yield assistant replies generated from queued notifications."""

        if await self._flush_notifications():
            async for part in self.continue_stream():
                yield part

    async def poll_notifications(self, *, for_user: bool = False) -> list[str]:
        """Check for VM notifications and returned files.

        Parameters
        ----------
        for_user:
            When ``True``, queue notifications for delivery to the client in
            addition to the agent.
        """

        if self._vm is None:
            return []

        notes = self._vm.fetch_notifications()
        returned = self._vm.fetch_returned_files()
        parts: list[str] = []

        for n in notes:
            await self._notification_queue.put(n)
            if for_user:
                await self._user_notification_queue.put(n)
            parts.append(n)

        for r in returned:
            try:
                data = r.read_bytes()
                encoded = base64.b64encode(data).decode()
            except Exception as exc:  # pragma: no cover - runtime errors
                _LOG.error("Failed to read returned file %s: %s", r, exc)
                continue
            try:
                r.unlink()
            except Exception as exc:  # pragma: no cover - runtime errors
                _LOG.warning("Failed to delete returned file %s: %s", r, exc)
            payload = json.dumps({"returned_file": r.name, "data": encoded})
            await self._notification_queue.put(payload)
            if for_user:
                await self._user_notification_queue.put(payload)
            parts.append(payload)

        if (
            (notes or returned)
            and self._state == "idle"
            and self._prompt_queue.empty()
            and (not self._worker or self._worker.done())
        ):
            async for part in self._deliver_notifications():
                parts.append(part)

        if for_user:
            while not self._user_notification_queue.empty():
                parts.append(await self._user_notification_queue.get())

        return parts

    async def _monitor_notifications(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._config.notification_poll_interval)
                await self.poll_notifications(for_user=False)
        except asyncio.CancelledError:  # pragma: no cover - lifecycle
            pass

    async def _watch_return_dir(self) -> None:
        """Watch the VM return queue and relay new files immediately."""
        if self._vm is None:
            return

        try:
            from watchfiles import awatch
            async for _ in awatch(self._vm.return_queue_dir):
                await self.poll_notifications(for_user=True)
        except asyncio.CancelledError:  # pragma: no cover - lifecycle
            pass

    async def _await_tool_and_followup(
        self,
        exec_task: asyncio.Task,
        follow_task: asyncio.Task,
        messages: list[Msg],
        conversation: Conversation,
        display_name: str,
    ) -> AsyncIterator[ChatResponse]:
        done, _ = await asyncio.wait(
            {exec_task, follow_task}, return_when=asyncio.FIRST_COMPLETED
        )

        name = display_name

        if exec_task in done:
            follow_task.cancel()
            with suppress(asyncio.CancelledError):
                await follow_task
            result = await exec_task
            self._current_tool_name = None
            self._add_tool_message(conversation, messages, name, result)
            async with self._lock:
                self._state = "generating"
                self._tool_task = None
            nxt = await self.ask(messages)
            self._add_assistant_message(conversation, messages, nxt.message)
            yield nxt
        else:
            followup = await follow_task
            self._add_assistant_message(conversation, messages, followup.message)
            yield followup
            result = await exec_task
            self._current_tool_name = None
            self._add_tool_message(conversation, messages, name, result)
            async with self._lock:
                self._state = "generating"
                self._tool_task = None
            nxt = await self.ask(messages)
            self._add_assistant_message(conversation, messages, nxt.message)
            yield nxt

    async def _process_tool_call(
        self,
        call: Message.ToolCall,
        messages: list[Msg],
        conversation: Conversation,
    ) -> AsyncIterator[ChatResponse]:
        func = self._tool_funcs.get(call.function.name)
        if not func:
            _LOG.warning("Unsupported tool call: %s", call.function.name)
            result = f"Unsupported tool: {call.function.name}"
            name = call.function.name
            self._add_tool_message(conversation, messages, name, result)
            return

        args = call.function.arguments
        if isinstance(args, str):
            with suppress(Exception):
                args = json.loads(args)

        if isinstance(args, Mapping) and "arguments" in args and set(args) <= {"name", "arguments"}:
            maybe_args = args.get("arguments")
            if isinstance(maybe_args, Mapping):
                args = maybe_args

        if not isinstance(args, Mapping):
            _LOG.warning("Invalid tool arguments for %s: %r", call.function.name, args)
            args = {}

        exec_task = asyncio.create_task(
            self._run_tool_async(func, **args)
        )

        if call.function.name == "send_to_agent":
            if isinstance(args, Mapping):
                display_name = str(args.get("name", "agent"))
            else:
                display_name = "agent"
        else:
            display_name = call.function.name
        self._current_tool_name = display_name

        follow_task = asyncio.create_task(self.ask(messages))
        async with self._lock:
            self._state = "awaiting_tool"
            self._tool_task = exec_task

        async for resp in self._await_tool_and_followup(
            exec_task, follow_task, messages, conversation, display_name
        ):
            yield resp

    async def _handle_tool_calls_stream(
        self,
        messages: List[Msg],
        response: ChatResponse,
        conversation: Conversation,
        depth: int = 0,
    ) -> AsyncIterator[ChatResponse]:
        if response.message.content:
            # Yield assistant content even when a tool call is present so context is not lost.
            yield response

        if not response.message.tool_calls:
            async with self._lock:
                self._state = "idle"
            return

        max_depth = self._config.max_tool_call_depth
        while depth < max_depth and response.message.tool_calls:
            # Handle each tool call sequentially so the model can react to
            # every tool's output before moving on to the next one.
            call = response.message.tool_calls.pop(0)
            async for nxt in self._process_tool_call(
                call, messages, conversation
            ):
                response = nxt
                yield nxt
            depth += 1

        async with self._lock:
            self._state = "idle"

    async def _generate_stream(
        self, prompt: str, extra: dict[str, str] | None = None
    ) -> AsyncIterator[str]:
        async with self._lock:
            if self._state == "awaiting_tool" and self._tool_task:
                async for part in self._chat_during_tool(prompt, extra):
                    yield part
                return
            self._state = "generating"

        prompt_with_extra = self._append_extra(prompt, extra)
        if self._persist and self._conversation:
            db.create_message(self._conversation, "user", prompt_with_extra)
        self._messages.append({"role": "user", "content": prompt_with_extra})

        response = await self.ask(self._messages)
        self._messages.append(response.message.model_dump())
        if self._persist and self._conversation:
            store_assistant_message(self._conversation, response.message)

        async for resp in self._handle_tool_calls_stream(
            self._messages, response, self._conversation
        ):
            text = format_output(resp.message)
            if text:
                yield text
        async for note in self._deliver_notifications():
            yield note

    async def _process_prompt_queue(self) -> None:
        try:
            while not self._prompt_queue.empty():
                prompt, extra, result_q = await self._prompt_queue.get()
                try:
                    async for part in self._generate_stream(prompt, extra):
                        await result_q.put(part)
                except Exception as exc:  # pragma: no cover - unforeseen errors
                    _LOG.exception("Error processing prompt: %s", exc)
                    await result_q.put(f"Error: {exc}")
                finally:
                    await result_q.put(None)
        finally:
            self._worker = None

    async def chat_stream(
        self, prompt: str, *, extra: dict[str, str] | None = None
    ) -> AsyncIterator[str]:
        async for note in self._deliver_notifications():
            yield note
        result_q: asyncio.Queue[str | None] = asyncio.Queue()
        await self._prompt_queue.put((prompt, extra, result_q))
        if not self._worker or self._worker.done():
            self._worker = asyncio.create_task(self._process_prompt_queue())

        while True:
            part = await result_q.get()
            if part is None:
                break
            yield part
        async for note in self._deliver_notifications():
            yield note

    async def continue_stream(self) -> AsyncIterator[str]:
        async with self._lock:
            if self._state != "idle":
                return
            self._state = "generating"

        response = await self.ask(self._messages)
        self._messages.append(response.message.model_dump())
        if self._persist and self._conversation:
            store_assistant_message(self._conversation, response.message)

        async for resp in self._handle_tool_calls_stream(
            self._messages, response, self._conversation
        ):
            text = format_output(resp.message)
            if text:
                yield text

    async def _chat_during_tool(
        self, prompt: str, extra: dict[str, str] | None = None
    ) -> AsyncIterator[str]:
        prompt_with_extra = self._append_extra(prompt, extra)
        if self._persist and self._conversation:
            db.create_message(self._conversation, "user", prompt_with_extra)
        self._messages.append({"role": "user", "content": prompt_with_extra})

        user_task = asyncio.create_task(self.ask(self._messages))
        exec_task = self._tool_task

        async for resp in self._await_tool_and_followup(
            exec_task,
            user_task,
            self._messages,
            self._conversation,
            self._current_tool_name or "tool",
        ):
            text = format_output(resp.message)
            if text:
                yield text
            async for part in self._handle_tool_calls_stream(
                self._messages, resp, self._conversation
            ):
                part_text = format_output(part.message)
                if part_text:
                    yield part_text
        async for note in self._deliver_notifications():
            yield note

from ..utils.debug import debug_all

debug_all(globals())
