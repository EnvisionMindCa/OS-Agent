from __future__ import annotations

from typing import List

from ollama import AsyncClient, ChatResponse

from .config import MAX_TOOL_CALL_DEPTH, MODEL_NAME, OLLAMA_HOST
from .db import Conversation, Message, _db, init_db
from .log import get_logger
from .schema import Msg
from .tools import add_two_numbers

_LOG = get_logger(__name__)


class ChatSession:
    def __init__(self, host: str = OLLAMA_HOST, model: str = MODEL_NAME) -> None:
        init_db()
        self._client = AsyncClient(host=host)
        self._model = model

    async def __aenter__(self) -> "ChatSession":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if not _db.is_closed():
            _db.close()

    async def ask(self, messages: List[Msg], *, think: bool = True) -> ChatResponse:
        return await self._client.chat(
            self._model,
            messages=messages,
            think=think,
            tools=[add_two_numbers],
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
                messages.append(
                    {
                        "role": "tool",
                        "name": call.function.name,
                        "content": str(result),
                    }
                )
                Message.create(
                    conversation=conversation,
                    role="tool",
                    content=str(result),
                )
                nxt = await self.ask(messages, think=True)
                Message.create(
                    conversation=conversation,
                    role="assistant",
                    content=nxt.message.content,
                )
                return await self._handle_tool_calls(
                    messages, nxt, conversation, depth + 1
                )

        return response

    async def chat(self, prompt: str) -> str:
        conversation = Conversation.create()
        Message.create(conversation=conversation, role="user", content=prompt)
        messages: List[Msg] = [{"role": "user", "content": prompt}]
        response = await self.ask(messages)
        messages.append(response.message.model_dump())
        Message.create(
            conversation=conversation,
            role="assistant",
            content=response.message.content,
        )

        _LOG.info("Thinking:\n%s", response.message.thinking or "<no thinking trace>")

        final_resp = await self._handle_tool_calls(messages, response, conversation)
        if final_resp is not response:
            # final response after handling tool calls
            Message.create(
                conversation=conversation,
                role="assistant",
                content=final_resp.message.content,
            )
        return final_resp.message.content
