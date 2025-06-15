"""Discord bot implementation."""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Iterable

import discord
from discord.ext import commands
from dotenv import load_dotenv

import agent
from agent.db import reset_history
from agent.utils.logging import get_logger
from agent.sessions.solo import SoloChatSession


class DiscordTeamBot(commands.Bot):
    """Discord bot for interacting with :class:`SoloChatSession`."""

    def __init__(self) -> None:
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)
        self._log = get_logger(__name__, level=logging.INFO)
        self._register_commands()

    # ------------------------------------------------------------------
    # Lifecycle events
    # ------------------------------------------------------------------
    async def on_ready(self) -> None:  # noqa: D401 - callback signature
        """Log a message once the bot has connected."""

        self._log.info("Logged in as %s", self.user)

    async def on_message(self, message: discord.Message) -> None:  # noqa: D401 - callback signature
        """Process incoming messages and stream chat replies."""

        if message.author.bot:
            return

        await self.process_commands(message)
        if message.content.startswith("!"):
            return

        docs = await self._handle_attachments(
            message.attachments, user_id=str(message.author.id)
        )
        if docs:
            info = "\n".join(f"{name} -> {path}" for name, path in docs)
            await message.reply(f"Uploaded:\n{info}", mention_author=False)

        if message.content.strip():
            try:
                async for part in agent.solo_chat(
                    message.content,
                    user=str(message.author.id),
                    session=str(message.channel.id),
                    think=False,
                ):
                    if part.get("tool_call"):
                        tc = part["tool_call"]
                        await message.reply(
                            f"**Running {tc['name']}**", mention_author=False
                        )
                    if msg := part.get("message"):
                        await message.reply(msg, mention_author=False)
            except Exception as exc:  # pragma: no cover - runtime errors
                self._log.error("Failed to process message: %s", exc)
                await message.reply(f"Error: {exc}", mention_author=False)

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------
    def _register_commands(self) -> None:
        @self.command(name="reset")
        async def reset(ctx: commands.Context) -> None:
            deleted = reset_history(str(ctx.author.id), str(ctx.channel.id))
            await ctx.reply(
                f"Chat history cleared ({deleted} messages deleted).",
            )

        @self.command(name="exec")
        async def exec_cmd(ctx: commands.Context, *, command: str) -> None:
            """Run ``command`` inside the user's VM and return the output."""

            output = await agent.vm_execute(command, user=str(ctx.author.id))
            output = output.strip()
            if not output:
                output = "(no output)"
            if len(output) > 1900:
                output = output[:1900] + "..."
            await ctx.reply(f"```\n{output}\n```", mention_author=False)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _handle_attachments(
        self,
        attachments: Iterable[discord.Attachment],
        *,
        user_id: str,
    ) -> list[tuple[str, str]]:
        """Download attachments and return their VM paths.

        Parameters
        ----------
        attachments:
            Iterable of Discord attachments to download.
        user_id:
            Identifier of the user uploading the attachments. This ensures
            documents are stored in the correct VM space.
        """

        if not attachments:
            return []

        uploaded: list[tuple[str, str]] = []
        tmpdir = Path(tempfile.mkdtemp(prefix="discord_upload_"))
        try:
            for attachment in attachments:
                dest = tmpdir / attachment.filename
                await attachment.save(dest)
                vm_path = await agent.upload_document(str(dest), user=user_id)
                uploaded.append((attachment.filename, vm_path))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        return uploaded


def run_bot(token: str) -> None:
    """Create and run the Discord bot."""

    DiscordTeamBot().run(token)


def main() -> None:
    """Load environment and start the bot."""

    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN environment variable not set")

    run_bot(token)


if __name__ == "__main__":  # pragma: no cover - manual execution
    main()

from agent.utils.debug import debug_all
debug_all(globals())

