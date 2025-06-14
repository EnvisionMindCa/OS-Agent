from __future__ import annotations

from typing import List, Literal, Optional, TypedDict

from ollama import Message


class Msg(TypedDict, total=False):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: Optional[str]
    tool_calls: Optional[List[Message.ToolCall]]


class ChatEvent(TypedDict, total=False):
    """Object yielded during chat streaming."""

    message: Optional[str]
    tool_call: Optional[dict]
    tool_result: Optional[dict]
    input_required: Optional[str]

