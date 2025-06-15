from __future__ import annotations

from .debug import debug
from ..config import LOG_LEVEL  # noqa: F401
import logging
from typing import Final

from colorama import Fore, Style, init as colorama_init

__all__: Final[list[str]] = ["get_logger"]


class _ColourFormatter(logging.Formatter):
    _COLOUR_FOR_LEVEL = {
        logging.DEBUG: Fore.GREEN,
        logging.INFO: Fore.WHITE,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.MAGENTA,
    }

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        colour = self._COLOUR_FOR_LEVEL.get(record.levelno, "")
        return f"{colour}{super().format(record)}{Style.RESET_ALL}"


@debug
def get_logger(name: str | None = None, level: int | None = None) -> logging.Logger:
    """Return a configured logger instance."""

    colorama_init()
    env_level = LOG_LEVEL.upper() if LOG_LEVEL else "INFO"
    if level is None:
        level = getattr(logging, env_level, logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(
        _ColourFormatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()
    logger.addHandler(handler)
    return logger
