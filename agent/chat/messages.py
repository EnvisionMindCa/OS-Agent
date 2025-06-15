from __future__ import annotations

import json
from typing import List

from ollama import Message

from .schema import Msg
from ..db import Conversation, db

__all__ = [
    "serialize_tool_calls",
    "format_output",
    "remove_tool_placeholder",
    "store_assistant_message",
]


def serialize_tool_calls(calls: List[Message.ToolCall]) -> str:
    """Return tool calls as a JSON string."""

    return json.dumps([c.model_dump() for c in calls])


def format_output(message: Message) -> str:
    """Return message content if present."""

    return message.content or ""


def remove_tool_placeholder(messages: List[Msg], placeholder: str) -> None:
    """Remove the pending placeholder message if present."""

    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        if msg.get("role") == "tool" and msg.get("content") == placeholder:
            messages.pop(i)
            break


def store_assistant_message(conversation: Conversation, message: Message) -> None:
    """Persist assistant messages, storing tool calls when present."""

    data = {"content": message.content or ""}
    if message.tool_calls:
        data["tool_calls"] = [c.model_dump() for c in message.tool_calls]

    db.create_message(
        conversation,
        "assistant",
        json.dumps(data),
    )


from ..utils.debug import debug_all
debug_all(globals())

