from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = ["ChatRequest", "ChatResponse", "ResetRequest", "ResetResponse"]

class ChatRequest(BaseModel):
    user: str = Field(..., example="default")
    session: str = Field(..., example="default")
    prompt: str = Field(..., min_length=1, example="Hello")

class ChatResponse(BaseModel):
    reply: str

class ResetRequest(BaseModel):
    user: str
    session: str

class ResetResponse(BaseModel):
    removed: int
