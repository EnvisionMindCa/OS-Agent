from __future__ import annotations

import json
from typing import List

from ollama import Message

from .schema import Msg
from ..db import Conversation, db

__all__ = [
    "serialize_tool_calls",
    "format_output",
    "store_assistant_message",
    "store_tool_message",
]


def serialize_tool_calls(calls: List[Message.ToolCall]) -> str:
    """Return tool calls as a JSON string."""

    return json.dumps([c.model_dump() for c in calls])


def format_output(message: Message) -> str:
    """Return message content if present."""

    return message.content or ""



def store_assistant_message(conversation: Conversation, message: Message) -> None:
    """Persist assistant messages, storing tool calls when present."""
    if not (message.content or message.tool_calls):
        # Nothing meaningful to store
        return

    data = {}
    if message.content:
        data["content"] = message.content
    if message.tool_calls:
        data["tool_calls"] = [c.model_dump() for c in message.tool_calls]

    db.create_message(
        conversation,
        "assistant",
        json.dumps(data),
    )


def store_tool_message(conversation: Conversation, name: str, content: str) -> None:
    """Persist tool messages with structured data."""

    data = {"name": name, "content": content}
    data = {str(k): str(v) for k, v in data.items() if v is not None}
    db.create_message(conversation, "tool", json.dumps(data))


from ..utils.debug import debug_all
debug_all(globals())

