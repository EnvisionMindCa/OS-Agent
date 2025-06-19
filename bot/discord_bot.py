"""Discord bot implementation."""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import Iterable, Tuple, List
import mimetypes

import discord
from discord.ext import commands
from dotenv import load_dotenv

from agent.db import delete_history
from agent.utils.logging import get_logger
from agent.utils.speech import transcribe_audio
from .ws_api import WSApiClient


class DiscordTeamBot(commands.Bot):
    """Discord bot interface using :class:`~agent.server` WebSocket API."""

    def __init__(self) -> None:
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)
        self._log = get_logger(__name__, level=logging.INFO)
        host = os.getenv("WS_API_HOST", "localhost")
        port = int(os.getenv("WS_API_PORT", 8765))
        self._client = WSApiClient(host=host, port=port)
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

        user = str(message.author.id)
        session_id = str(message.channel.id)

        docs, transcripts = await self._handle_attachments(
            message.attachments,
            user=user,
            session=session_id,
        )
        if docs:
            info = "\n".join(f"{name} -> {path}" for name, path in docs)
            await message.reply(f"Uploaded:\n{info}", mention_author=False)
        for text in transcripts:
            try:
                speech_prompt = f"[speech] {text}"
                async for part in self._client.team_chat_stream(
                    speech_prompt,
                    user=user,
                    session=session_id,
                    think=False,
                    extra={
                        "user_name": str(message.author.name),
                        "channel_name": str(message.channel.name),
                    },
                ):
                    await message.reply(part, mention_author=False)
            except Exception as exc:  # pragma: no cover - runtime errors
                self._log.error("Failed to process speech: %s", exc)
                await message.reply(f"Error: {exc}", mention_author=False)

        if message.content.strip():
            try:
                async for part in self._client.team_chat_stream(
                    message.content,
                    user=user,
                    session=session_id,
                    think=False,
                ):
                    await message.reply(part, mention_author=False)
            except Exception as exc:  # pragma: no cover - runtime errors
                self._log.error("Failed to process message: %s", exc)
                await message.reply(f"Error: {exc}", mention_author=False)

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------
    def _register_commands(self) -> None:
        @self.command(name="reset")
        async def reset(ctx: commands.Context) -> None:
            deleted = delete_history(str(ctx.author.id), str(ctx.channel.id))
            await ctx.reply(
                f"Chat history cleared ({deleted} messages deleted).",
            )

        @self.command(name="exec")
        async def exec_cmd(ctx: commands.Context, *, command: str) -> None:
            """Run ``command`` inside the user's VM and return the output."""

            try:
                resp = await ctx.bot._client.request(
                    "vm_execute",
                    user=str(ctx.author.id),
                    session=str(ctx.channel.id),
                    think=False,
                    command=command,
                    timeout=30.0,
                )
                output = str(resp.get("result", "")).strip()
            except Exception as exc:
                await ctx.reply(f"Error: {exc}", mention_author=False)
                return

            if not output:
                output = "(no output)"
            if len(output) > 1900:
                output = output[:1900] + "..."
            await ctx.reply(f"```\n{output}\n```", mention_author=False)

        @self.command(name="shutdown")
        @commands.has_permissions(administrator=True)
        async def shutdown_cmd(ctx: commands.Context) -> None:
            """Shut down the bot. Only administrators can invoke this."""

            await ctx.reply("Shutting down...", mention_author=False)
            await ctx.bot.close()

        @shutdown_cmd.error
        async def shutdown_cmd_error(
            ctx: commands.Context, exc: commands.CommandError
        ) -> None:
            if isinstance(exc, commands.MissingPermissions):
                await ctx.reply(
                    "You do not have permission to shut down the bot.",
                    mention_author=False,
                )
            else:  # pragma: no cover - runtime errors
                await ctx.reply(f"Error: {exc}", mention_author=False)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _handle_attachments(
        self,
        attachments: Iterable[discord.Attachment],
        *,
        user: str,
        session: str,
    ) -> Tuple[List[Tuple[str, str]], List[str]]:
        """Download attachments and return their VM paths and audio transcripts.

        Parameters
        ----------
        attachments:
            Iterable of Discord attachments to download.
        user, session:
            WebSocket session identifiers used for file upload.
        """

        if not attachments:
            return [], []

        uploaded: List[Tuple[str, str]] = []
        transcripts: List[str] = []
        tmpdir = Path(tempfile.mkdtemp(prefix="discord_upload_"))
        try:
            for attachment in attachments:
                dest = tmpdir / attachment.filename
                await attachment.save(dest)
                mime, _ = mimetypes.guess_type(attachment.filename)
                if mime and mime.startswith("audio"):
                    try:
                        text = await transcribe_audio(str(dest))
                        if text:
                            transcripts.append(text)
                    except Exception as exc:  # pragma: no cover - runtime errors
                        self._log.error("Transcription failed for %s: %s", attachment.filename, exc)
                else:
                    try:
                        resp = await self._client.request(
                            "upload_document",
                            user=user,
                            session=session,
                            think=False,
                            file_path=str(dest),
                        )
                        vm_path = str(resp.get("result", ""))
                        uploaded.append((attachment.filename, vm_path))
                    except Exception as exc:  # pragma: no cover - runtime errors
                        self._log.error("Upload failed for %s: %s", attachment.filename, exc)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        return uploaded, transcripts


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

