from __future__ import annotations

from typing import List
import json

from ollama import Message

from .db import Conversation, Message as DBMessage
from .schema import Msg


def load_history(conversation: Conversation) -> List[Msg]:
    """Return chat history for ``conversation``.

    System messages are skipped. Assistant messages are parsed for tool
    calls, falling back to plain text when JSON decoding fails.
    """
    messages: List[Msg] = []
    for msg in conversation.messages.order_by(DBMessage.created_at):
        if msg.role == "system":
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
