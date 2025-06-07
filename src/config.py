from __future__ import annotations

import os
from pathlib import Path
from typing import Final

MODEL_NAME: Final[str] = os.getenv("OLLAMA_MODEL", "qwen3:1.7b")
OLLAMA_HOST: Final[str] = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MAX_TOOL_CALL_DEPTH: Final[int] = 5
NUM_CTX: Final[int] = int(os.getenv("OLLAMA_NUM_CTX", "16000"))
UPLOAD_DIR: Final[str] = os.getenv("UPLOAD_DIR", str(Path.cwd() / "uploads"))
VM_IMAGE: Final[str] = os.getenv("VM_IMAGE", "docker/Dockerfile.vm")

SYSTEM_PROMPT: Final[str] = (
    "You are Starlette, a professional AI assistant with advanced tool orchestration. "
    "Always analyze the user's objective before responding. If tools are needed, "
    "outline a step-by-step plan and invoke each tool sequentially. Shell commands "
    "execute asynchronously, so provide a brief interim reply while waiting. Once a "
    "tool returns its result you will receive a tool message and must continue from "
    "there. If the result arrives before your interim reply is complete, cancel the "
    "reply and incorporate the tool output instead. Uploaded files live under /data "
    "and are accessible via the execute_terminal tool. When you are unsure about any "
    "detail, you must use execute_terminal to search the internet or inspect files "
    "before answering. Continue using tools until you have gathered everything "
    "required to produce an accurate answer, then craft a clear and precise final "
    "response that fully addresses the request."
)
