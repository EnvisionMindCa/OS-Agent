"""Implementation of a Discord bot that uses the LLM backend."""

from __future__ import annotations


import discord
from discord.ext import commands

from src.chat import ChatSession
from src.log import get_logger

from .config import DEFAULT_SESSION, DEFAULT_USER_PREFIX, DISCORD_TOKEN

__all__ = ["LLMDiscordBot", "run_bot"]


class LLMDiscordBot(commands.Bot):
    """Discord bot that interfaces with :class:`ChatSession`."""

    def __init__(self, *, intents: discord.Intents | None = None) -> None:
        intents = intents or discord.Intents.all()
        super().__init__(command_prefix=None, intents=intents)
        self._log = get_logger(self.__class__.__name__)

    async def on_ready(self) -> None:  # noqa: D401
        self._log.info("Logged in as %s (%s)", self.user, self.user.id)

    async def on_message(self, message: discord.Message) -> None:  # noqa: D401
        if message.author.bot or not message.content.strip():
            return

        user_id = f"{DEFAULT_USER_PREFIX}{message.author.id}"
        session_id = f"{DEFAULT_SESSION}_{message.channel.id}"

        self._log.debug("Received message from %s: %s", user_id, message.content)

        async with ChatSession(user=user_id, session=session_id) as chat:
            try:
                reply = await chat.chat(message.content)
            except Exception:
                self._log.exception("Failed to generate reply")
                return

        if reply:
            await message.channel.send(reply)


def run_bot(token: str | None = None) -> None:
    """Run the Discord bot using the provided token."""
    token = token or DISCORD_TOKEN
    if not token:
        raise RuntimeError("Discord token not provided")

    bot = LLMDiscordBot()
    bot.run(token)


if __name__ == "__main__":  # pragma: no cover - manual start
    run_bot()
