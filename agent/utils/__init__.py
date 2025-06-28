"""Utility functions exposed at package level."""

from .memory import get_memory, set_memory, edit_memory
from .pty_runner import PTYProcess

__all__ = [
    "transcribe_audio",
    "get_memory",
    "set_memory",
    "edit_memory",
    "PTYProcess",
]


def transcribe_audio(file_path: str, model_size: str = "tiny.en") -> str:
    """Lazy wrapper around :func:`~agent.utils.speech.transcribe_audio`.

    The optional :mod:`whisper` dependency is imported on demand so that
    environments without the library can still use most of the package
    functionality. A clear ``ImportError`` is raised if transcription is
    attempted when the dependency is missing.
    """

    try:
        from .speech import transcribe_audio as _transcribe
    except Exception as exc:  # pragma: no cover - optional dependency
        raise ImportError("`whisper` is required for audio transcription") from exc

    return _transcribe(file_path, model_size=model_size)

