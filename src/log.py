from __future__ import annotations

import logging
from typing import Final

from colorama import Fore, Style, init as colorama_init

__all__: Final[list[str]] = ["get_logger"]


class _ColourFormatter(logging.Formatter):
    _COLOUR_FOR_LEVEL = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.MAGENTA,
    }

    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        colour = self._COLOUR_FOR_LEVEL.get(record.levelno, "")
        return f"{colour}{super().format(record)}{Style.RESET_ALL}"


def get_logger(name: str | None = None, level: int = logging.INFO) -> logging.Logger:
    colorama_init()
    handler = logging.StreamHandler()
    handler.setFormatter(_ColourFormatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()
    logger.addHandler(handler)
    return logger
