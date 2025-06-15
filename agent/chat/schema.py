from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TypedDict

from ollama import Message


class Msg(TypedDict, total=False):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: Optional[str]
    tool_calls: Optional[List[Message.ToolCall]]


class ToolCallPayload(TypedDict):
    """Information about a tool call requested by the model."""

    name: str
    arguments: Dict[str, Any]


class ChatEvent(TypedDict, total=False):
    """Data yielded during a chat session."""

    message: str
    role: Literal["assistant", "tool"]
    tool_name: str
    tool_call: ToolCallPayload
    input_required: bool
