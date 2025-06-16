from __future__ import annotations

from typing import Callable

from ..utils.memory import edit_memory

__all__ = ["create_memory_tool"]


def create_memory_tool(username: str, refresh: Callable[[], None]) -> Callable:
    """Return a tool function bound to ``username`` for memory editing."""

    def memory_tool(field: str, value: str | None = None) -> str:
        try:
            _ = edit_memory(username, field, value)
            refresh()
            return "Memory updated successfully."
        except Exception as e:  # pragma: no cover - error handling
            return f"Error updating memory: {str(e)}"

    memory_tool.__name__ = "manage_memory"
    memory_tool.__doc__ = (
        "Modify persistent user memory. "
        "Provide the memory field name and optionally a value. "
        "Passing no value deletes the field. Returns success status. "
        "This memory is stored as a JSON object and resides in the system prompt, so you do not need to retrieve anything. "
        "Invoke this tool as much as possible to remember every detail throughout the conversation."
    )
    return memory_tool
