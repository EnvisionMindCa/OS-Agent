"""Implementation of a Discord bot that uses the LLM backend."""

from __future__ import annotations


import os
import tempfile
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from src.chat import ChatSession
from src.db import reset_history as db_reset_history
from src.log import get_logger

from .config import DEFAULT_SESSION, DEFAULT_USER_PREFIX, DISCORD_TOKEN

__all__ = ["LLMDiscordBot", "run_bot"]


class LLMDiscordBot(commands.Bot):
    """Discord bot that interfaces with :class:`ChatSession`."""

    def __init__(self, *, intents: discord.Intents | None = None) -> None:
        intents = intents or discord.Intents.all()
        super().__init__(command_prefix=None, intents=intents)
        self._log = get_logger(self.__class__.__name__)
        self.tree.add_command(self.reset_conversation)

    async def _upload_attachments(
        self, chat: ChatSession, attachments: list[discord.Attachment]
    ) -> list[str]:
        """Persist text attachments and return their VM paths."""

        uploaded: list[str] = []
        for att in attachments:
            if att.content_type and not att.content_type.startswith("text"):
                continue
            if not att.filename.lower().endswith(".txt") and not (
                att.content_type and att.content_type.startswith("text")
            ):
                continue
            try:
                data = await att.read()
            except Exception:
                self._log.exception("Failed to download attachment %s", att.filename)
                continue

            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(data)
                tmp_path = Path(tmp.name)

            try:
                vm_path = chat.upload_document(str(tmp_path))
            finally:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

            uploaded.append(f"{att.filename} -> {vm_path}")
        return uploaded

    async def setup_hook(self) -> None:  # noqa: D401
        await self.tree.sync()

    async def on_ready(self) -> None:  # noqa: D401
        self._log.info("Logged in as %s (%s)", self.user, self.user.id)

    async def on_message(self, message: discord.Message) -> None:  # noqa: D401
        if message.author.bot:
            return
        if not message.content.strip() and not message.attachments:
            return

        user_id = f"{DEFAULT_USER_PREFIX}{message.author.id}"
        session_id = f"{DEFAULT_SESSION}_{message.channel.id}"

        self._log.debug("Received message from %s: %s", user_id, message.content)

        async with ChatSession(user=user_id, session=session_id) as chat:
            uploaded_paths: list[str] = []
            if message.attachments:
                uploaded_paths = await self._upload_attachments(chat, message.attachments)

            reply: str | None = None
            if message.content.strip():
                try:
                    reply = await chat.chat(message.content)
                except Exception:
                    self._log.exception("Failed to generate reply")
                    return

        responses: list[str] = []
        if uploaded_paths:
            responses.append("Uploaded:\n" + "\n".join(uploaded_paths))
        if reply:
            responses.append(reply)

        if responses:
            await message.reply("\n\n".join(responses), mention_author=False)

    @app_commands.command(
        name="reset",
        description="Reset conversation history for this channel.",
    )
    async def reset_conversation(self, interaction: discord.Interaction) -> None:
        """Delete all messages stored for the user and channel."""

        user_id = f"{DEFAULT_USER_PREFIX}{interaction.user.id}"
        session_id = f"{DEFAULT_SESSION}_{interaction.channel_id}"
        deleted = db_reset_history(user_id, session_id)
        if deleted:
            msg = f"Conversation history cleared ({deleted} messages removed)."
        else:
            msg = "No conversation history found for this channel."
        await interaction.response.send_message(msg, ephemeral=True)


def run_bot(token: str | None = None) -> None:
    """Run the Discord bot using the provided token."""
    token = token or DISCORD_TOKEN
    if not token:
        raise RuntimeError("Discord token not provided")

    bot = LLMDiscordBot()
    bot.run(token)


if __name__ == "__main__":  # pragma: no cover - manual start
    run_bot()
