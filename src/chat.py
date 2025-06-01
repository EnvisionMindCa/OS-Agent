from __future__ import annotations

from typing import List
import json

from ollama import AsyncClient, ChatResponse, Message

from .config import MAX_TOOL_CALL_DEPTH, MODEL_NAME, OLLAMA_HOST
from .db import Conversation, Message as DBMessage, User, _db, init_db
from .log import get_logger
from .schema import Msg
from .tools import add_two_numbers, execute_python

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
        self._messages: List[Msg] = self._load_history()

    async def __aenter__(self) -> "ChatSession":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if not _db.is_closed():
            _db.close()

    def _load_history(self) -> List[Msg]:
        messages: List[Msg] = []
        for msg in self._conversation.messages.order_by(DBMessage.created_at):
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

    @staticmethod
    def _store_assistant_message(
        conversation: Conversation, message: Message
    ) -> None:
        """Persist assistant messages, storing tool calls when present."""

        if message.tool_calls:
            content = json.dumps([c.model_dump() for c in message.tool_calls])
        else:
            content = message.content or ""

        DBMessage.create(conversation=conversation, role="assistant", content=content)

    async def ask(self, messages: List[Msg], *, think: bool = True) -> ChatResponse:
        return await self._client.chat(
            self._model,
            messages=messages,
            think=think,
            tools=[add_two_numbers, execute_python],
        )

    async def _handle_tool_calls(
        self,
        messages: List[Msg],
        response: ChatResponse,
        conversation: Conversation,
        depth: int = 0,
    ) -> ChatResponse:
        if depth >= MAX_TOOL_CALL_DEPTH or not response.message.tool_calls:
            return response

        for call in response.message.tool_calls:
            if call.function.name == "add_two_numbers":
                result = add_two_numbers(**call.function.arguments)
            elif call.function.name == "execute_python":
                result = execute_python(**call.function.arguments)
            else:
                continue

            messages.append(
                {
                    "role": "tool",
                    "name": call.function.name,
                    "content": str(result),
                }
            )
            DBMessage.create(
                conversation=conversation,
                role="tool",
                content=str(result),
            )
            nxt = await self.ask(messages, think=True)
            self._store_assistant_message(conversation, nxt.message)
            return await self._handle_tool_calls(
                messages, nxt, conversation, depth + 1
            )

        return response

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
        return final_resp.message.content
