"""Configuration for the Discord bot."""

from __future__ import annotations

import os
from typing import Final

# Discord bot token
DISCORD_TOKEN: Final[str | None] = os.getenv("DISCORD_TOKEN")

# Default values for chat sessions
DEFAULT_USER_PREFIX: Final[str] = "discord_"
DEFAULT_SESSION: Final[str] = "discord"
