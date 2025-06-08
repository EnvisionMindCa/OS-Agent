from __future__ import annotations

from typing import List, AsyncIterator
from dataclasses import dataclass, field
import json
import asyncio
import shutil
from pathlib import Path

from ollama import AsyncClient, ChatResponse, Message

from .config import (
    MAX_TOOL_CALL_DEPTH,
    MODEL_NAME,
    NUM_CTX,
    OLLAMA_HOST,
    SYSTEM_PROMPT,
    UPLOAD_DIR,
)
from .db import (
    Conversation,
    Message as DBMessage,
    User,
    _db,
    init_db,
    add_document,
)
from .log import get_logger
from .schema import Msg
from .tools import execute_terminal, execute_terminal_async, set_vm
from .vm import VMRegistry


@dataclass
class _SessionData:
    """Shared state for each conversation session."""

    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    state: str = "idle"
    tool_task: asyncio.Task | None = None


_SESSION_DATA: dict[int, _SessionData] = {}


def _get_session_data(conv_id: int) -> _SessionData:
    data = _SESSION_DATA.get(conv_id)
    if data is None:
        data = _SessionData()
        _SESSION_DATA[conv_id] = data
    return data


_LOG = get_logger(__name__)


class ChatSession:
    def __init__(
        self,
        user: str = "default",
        session: str = "default",
        host: str = OLLAMA_HOST,
        model: str = MODEL_NAME,
    ) -> None:
        init_db()
        self._client = AsyncClient(host=host)
        self._model = model
        self._user, _ = User.get_or_create(username=user)
        self._conversation, _ = Conversation.get_or_create(
            user=self._user, session_name=session
        )
        self._vm = None
        self._messages: List[Msg] = self._load_history()
        self._data = _get_session_data(self._conversation.id)
        self._lock = self._data.lock

    # Shared state properties -------------------------------------------------

    @property
    def _state(self) -> str:
        return self._data.state

    @_state.setter
    def _state(self, value: str) -> None:
        self._data.state = value

    @property
    def _tool_task(self) -> asyncio.Task | None:
        return self._data.tool_task

    @_tool_task.setter
    def _tool_task(self, task: asyncio.Task | None) -> None:
        self._data.tool_task = task

    async def __aenter__(self) -> "ChatSession":
        self._vm = VMRegistry.acquire(self._user.username)
        set_vm(self._vm)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        set_vm(None)
        if self._vm:
            VMRegistry.release(self._user.username)
        if not _db.is_closed():
            _db.close()

    def upload_document(self, file_path: str) -> str:
        """Save a document for later access inside the VM.

        The file is copied into ``UPLOAD_DIR`` and recorded in the database. The
        returned path is the location inside the VM (prefixed with ``/data``).
        """

        src = Path(file_path)
        if not src.exists():
            raise FileNotFoundError(file_path)

        dest = Path(UPLOAD_DIR) / self._user.username
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / src.name
        shutil.copy(src, target)
        add_document(self._user.username, str(target), src.name)
        return f"/data/{src.name}"

    def _load_history(self) -> List[Msg]:
        messages: List[Msg] = []
        for msg in self._conversation.messages.order_by(DBMessage.created_at):
            if msg.role == "system":
                # Skip persisted system prompts from older versions
                continue
            if msg.role == "assistant":
                try:
                    calls = json.loads(msg.content)
                except json.JSONDecodeError:
                    messages.append({"role": "assistant", "content": msg.content})
                else:
                    messages.append(
                        {
                            "role": "assistant",
                            "tool_calls": [Message.ToolCall(**c) for c in calls],
                        }
                    )
            elif msg.role == "user":
                messages.append({"role": "user", "content": msg.content})
            else:
                messages.append({"role": "tool", "content": msg.content})
        return messages

    # ------------------------------------------------------------------
    @staticmethod
    def _serialize_tool_calls(calls: List[Message.ToolCall]) -> str:
        """Convert tool calls to a JSON string for storage or output."""

        return json.dumps([c.model_dump() for c in calls])

    @staticmethod
    def _format_output(message: Message) -> str:
        """Return tool calls as JSON or message content if present."""

        # if message.tool_calls:
        #     return ChatSession._serialize_tool_calls(message.tool_calls)
        return message.content or ""

    @staticmethod
    def _store_assistant_message(conversation: Conversation, message: Message) -> None:
        """Persist assistant messages, storing tool calls when present."""

        if message.tool_calls:
            content = ChatSession._serialize_tool_calls(message.tool_calls)
        else:
            content = message.content or ""

        if content.strip():
            DBMessage.create(conversation=conversation, role="assistant", content=content)

    async def ask(self, messages: List[Msg], *, think: bool = True) -> ChatResponse:
        """Send a chat request, automatically prepending the system prompt."""

        if not messages or messages[0].get("role") != "system":
            payload = [{"role": "system", "content": SYSTEM_PROMPT}, *messages]
        else:
            payload = messages

        return await self._client.chat(
            self._model,
            messages=payload,
            think=think,
            tools=[execute_terminal],
            options={"num_ctx": NUM_CTX},
        )

    async def _handle_tool_calls_stream(
        self,
        messages: List[Msg],
        response: ChatResponse,
        conversation: Conversation,
        depth: int = 0,
    ) -> AsyncIterator[ChatResponse]:
        if not response.message.tool_calls:
            if response.message.content:
                yield response
            async with self._lock:
                self._state = "idle"
            return
        while depth < MAX_TOOL_CALL_DEPTH and response.message.tool_calls:
            for call in response.message.tool_calls:
                if call.function.name != "execute_terminal":
                    _LOG.warning("Unsupported tool call: %s", call.function.name)
                    result = f"Unsupported tool: {call.function.name}"
                    messages.append(
                        {
                            "role": "tool",
                            "name": call.function.name,
                            "content": result,
                        }
                    )
                    DBMessage.create(
                        conversation=conversation,
                        role="tool",
                        content=result,
                    )
                    continue

                exec_task = asyncio.create_task(
                    execute_terminal_async(**call.function.arguments)
                )
                follow_task = asyncio.create_task(self.ask(messages, think=True))

                async with self._lock:
                    self._state = "awaiting_tool"
                    self._tool_task = exec_task

                done, _ = await asyncio.wait(
                    {exec_task, follow_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if exec_task in done:
                    follow_task.cancel()
                    try:
                        await follow_task
                    except asyncio.CancelledError:
                        pass
                    result = await exec_task
                    messages.append(
                        {
                            "role": "tool",
                            "name": call.function.name,
                            "content": result,
                        }
                    )
                    DBMessage.create(
                        conversation=conversation,
                        role="tool",
                        content=result,
                    )
                    async with self._lock:
                        self._state = "generating"
                        self._tool_task = None
                    nxt = await self.ask(messages, think=True)
                    self._store_assistant_message(conversation, nxt.message)
                    messages.append(nxt.message.model_dump())
                    response = nxt
                    yield nxt
                else:
                    followup = await follow_task
                    self._store_assistant_message(conversation, followup.message)
                    messages.append(followup.message.model_dump())
                    yield followup
                    result = await exec_task
                    messages.append(
                        {
                            "role": "tool",
                            "name": call.function.name,
                            "content": result,
                        }
                    )
                    DBMessage.create(
                        conversation=conversation,
                        role="tool",
                        content=result,
                    )
                    async with self._lock:
                        self._state = "generating"
                        self._tool_task = None
                    nxt = await self.ask(messages, think=True)
                    self._store_assistant_message(conversation, nxt.message)
                    messages.append(nxt.message.model_dump())
                    response = nxt
                    yield nxt

                depth += 1

        async with self._lock:
            self._state = "idle"

    async def _handle_tool_calls(
        self,
        messages: List[Msg],
        response: ChatResponse,
        conversation: Conversation,
        depth: int = 0,
    ) -> ChatResponse:
        final = response
        gen = self._handle_tool_calls_stream(messages, response, conversation, depth)
        async for final in gen:
            pass
        return final

    async def chat(self, prompt: str) -> str:
        DBMessage.create(conversation=self._conversation, role="user", content=prompt)
        self._messages.append({"role": "user", "content": prompt})

        response = await self.ask(self._messages)
        self._messages.append(response.message.model_dump())
        self._store_assistant_message(self._conversation, response.message)

        _LOG.info("Thinking:\n%s", response.message.thinking or "<no thinking trace>")

        final_resp = await self._handle_tool_calls(
            self._messages, response, self._conversation
        )
        return self._format_output(final_resp.message)

    async def chat_stream(self, prompt: str) -> AsyncIterator[str]:
        async with self._lock:
            if self._state == "generating":
                _LOG.info("Ignoring message while generating")
                return
            if self._state == "awaiting_tool" and self._tool_task:
                async for part in self._chat_during_tool(prompt):
                    yield part
                return
            self._state = "generating"

        DBMessage.create(conversation=self._conversation, role="user", content=prompt)
        self._messages.append({"role": "user", "content": prompt})

        response = await self.ask(self._messages)
        self._messages.append(response.message.model_dump())
        self._store_assistant_message(self._conversation, response.message)

        _LOG.info("Thinking:\n%s", response.message.thinking or "<no thinking trace>")

        async for resp in self._handle_tool_calls_stream(
            self._messages, response, self._conversation
        ):
            text = self._format_output(resp.message)
            if text:
                yield text

    async def _chat_during_tool(self, prompt: str) -> AsyncIterator[str]:
        DBMessage.create(conversation=self._conversation, role="user", content=prompt)
        self._messages.append({"role": "user", "content": prompt})

        user_task = asyncio.create_task(self.ask(self._messages))
        exec_task = self._tool_task

        done, _ = await asyncio.wait(
            {exec_task, user_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        if exec_task in done:
            user_task.cancel()
            try:
                await user_task
            except asyncio.CancelledError:
                pass
            result = await exec_task
            self._tool_task = None
            self._messages.append(
                {"role": "tool", "name": "execute_terminal", "content": result}
            )
            DBMessage.create(
                conversation=self._conversation, role="tool", content=result
            )
            async with self._lock:
                self._state = "generating"
            nxt = await self.ask(self._messages, think=True)
            self._store_assistant_message(self._conversation, nxt.message)
            self._messages.append(nxt.message.model_dump())
            text = self._format_output(nxt.message)
            if text:
                yield text
            async for part in self._handle_tool_calls_stream(
                self._messages, nxt, self._conversation
            ):
                text = self._format_output(part.message)
                if text:
                    yield text
        else:
            resp = await user_task
            self._store_assistant_message(self._conversation, resp.message)
            self._messages.append(resp.message.model_dump())
            async with self._lock:
                self._state = "awaiting_tool"
            text = self._format_output(resp.message)
            if text:
                yield text
            result = await exec_task
            self._tool_task = None
            self._messages.append(
                {"role": "tool", "name": "execute_terminal", "content": result}
            )
            DBMessage.create(
                conversation=self._conversation, role="tool", content=result
            )
            async with self._lock:
                self._state = "generating"
            nxt = await self.ask(self._messages, think=True)
            self._store_assistant_message(self._conversation, nxt.message)
            self._messages.append(nxt.message.model_dump())
            text = self._format_output(nxt.message)
            if text:
                yield text
            async for part in self._handle_tool_calls_stream(
                self._messages, nxt, self._conversation
            ):
                text = self._format_output(part.message)
                if text:
                    yield text
