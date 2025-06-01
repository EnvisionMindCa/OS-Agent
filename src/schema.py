from __future__ import annotations

from typing import List, Literal, Optional, TypedDict

from ollama import Message


class Msg(TypedDict, total=False):
    role: Literal["user", "assistant", "tool"]
    content: str
    name: Optional[str]
    tool_calls: Optional[List[Message.ToolCall]]
