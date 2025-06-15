from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Final

import whisper

__all__: Final = ["transcribe_audio"]

@lru_cache(maxsize=1)
def _load_model(size: str = "base"):
    return whisper.load_model(size)

async def transcribe_audio(file_path: str, model_size: str = "base") -> str:
    """Return the transcription of ``file_path`` using Whisper."""
    model = _load_model(model_size)
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, lambda: model.transcribe(file_path))
    text: str = result.get("text", "").strip()
    return text


