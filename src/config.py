from __future__ import annotations

import os
from typing import Final

MODEL_NAME: Final[str] = os.getenv("OLLAMA_MODEL", "qwen3")
OLLAMA_HOST: Final[str] = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MAX_TOOL_CALL_DEPTH: Final[int] = 5
NUM_CTX: Final[int] = int(os.getenv("OLLAMA_NUM_CTX", "32000"))
