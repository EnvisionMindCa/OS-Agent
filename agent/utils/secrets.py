from __future__ import annotations

__all__ = ["get_secret"]

import os
from getpass import getpass

from .debug import debug_all

from .logging import get_logger

_LOG = get_logger(__name__)


def get_secret(name: str, prompt: str | None = None) -> str:
    """Return a secret value from the environment or ask the operator.

    Parameters
    ----------
    name:
        Name of the environment variable to retrieve.
    prompt:
        Optional prompt to display when requesting the secret interactively.

    Returns
    -------
    str
        The secret value.

    Notes
    -----
    When the value is not available in the environment, the function falls back
    to :func:`getpass.getpass` so the secret is not echoed back to the console.
    """
    value = os.getenv(name)
    if value:
        return value

    msg = prompt or f"Enter value for {name}: "
    try:
        return getpass(msg)
    except Exception as exc:  # pragma: no cover - unforeseen errors
        _LOG.error("Failed to obtain secret %s: %s", name, exc)
        raise RuntimeError(f"Secret {name} not provided") from exc


debug_all(globals())
