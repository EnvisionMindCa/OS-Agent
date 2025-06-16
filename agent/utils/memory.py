from __future__ import annotations

import json

from ..config import DEFAULT_MEMORY_TEMPLATE, MEMORY_LIMIT
from ..db import db

__all__ = ["get_memory", "set_memory", "edit_memory", "edit_protected_memory"]


def get_memory(username: str) -> str:
    """Return the persisted memory for ``username`` creating defaults."""
    db.init_db()
    user = db.get_or_create_user(username)
    memory = getattr(user, "memory", "")
    if not memory:
        memory = DEFAULT_MEMORY_TEMPLATE
        user.memory = memory
        user.save()
    return memory


def set_memory(username: str, memory: str) -> str:
    """Persist ``memory`` for ``username`` ensuring size limits."""
    memory = memory.strip()
    if len(memory) > MEMORY_LIMIT:
        memory = memory[:MEMORY_LIMIT]
    db.init_db()
    user = db.get_or_create_user(username)
    user.memory = memory
    user.save()
    return memory


def edit_memory(username: str, field: str, value: str | None = None) -> str:
    """Add, update or remove ``field`` in ``username``'s memory.

    If ``value`` is provided, the field is set to that value. When ``value`` is
    ``None``, the field is removed. Memory is stored as a JSON object.
    """
    text = get_memory(username)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = {}
    if value is None:
        data.pop(field, None)
    else:
        data[field] = value
    memory = json.dumps(data, ensure_ascii=False, indent=2)
    return set_memory(username, memory)


def edit_protected_memory(username: str, field: str, value: str | None = None) -> str:
    """Add, update or remove ``field`` in ``username``'s protected memory.

    The protected memory dictionary is stored under the ``protected_memory`` key
    inside the main memory JSON object. Only user code should invoke this
    function as the LLM agent is not allowed to modify protected memory.
    """

    text = get_memory(username)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = {}

    protected = data.get("protected_memory")
    if not isinstance(protected, dict):
        protected = {}
    if value is None:
        protected.pop(field, None)
    else:
        protected[field] = value

    data["protected_memory"] = protected

    memory = json.dumps(data, ensure_ascii=False, indent=2)
    return set_memory(username, memory)
