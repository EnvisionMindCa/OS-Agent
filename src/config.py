from __future__ import annotations

import os
from typing import Final

MODEL_NAME: Final[str] = os.getenv("OLLAMA_MODEL", "qwen3:1.7b")
EMBEDDING_MODEL_NAME: Final[str] = os.getenv("OLLAMA_EMBEDDING_MODEL", "snowflake-arctic-embed:137m")   # unused for now
OLLAMA_HOST: Final[str] = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MAX_TOOL_CALL_DEPTH: Final[int] = 5
NUM_CTX: Final[int] = int(os.getenv("OLLAMA_NUM_CTX", "16000"))

SYSTEM_PROMPT: Final[str] = (
    "You are a versatile AI assistant named Starlette able to orchestrate several tools to "
    "complete tasks. Plan your responses carefully and, when needed, call one "
    "or more tools consecutively to gather data, compute answers, or transform "
    "information. Continue chaining tools until the user's request is fully "
    "addressed and then deliver a concise, coherent final reply."
)
