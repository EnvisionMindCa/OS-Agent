"""Discord bot implementation."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import tempfile
import base64
import json
from io import BytesIO
from pathlib import Path
from typing import Iterable, Tuple, List
import mimetypes

import discord
from discord.ext import commands
from dotenv import load_dotenv

from agent.db import delete_history
from agent.utils.logging import get_logger
from agent import transcribe_audio
from .ws_api import WSApiClient, WSConnection


class DiscordTeamBot(commands.Bot):
    """Discord bot interface using :class:`~agent.server` WebSocket API."""

    def __init__(self) -> None:
        intents = discord.Intents.all()
        super().__init__(command_prefix="!", intents=intents)
        self._log = get_logger(__name__, level=logging.INFO)
        host = os.getenv("WS_API_HOST", "localhost")
        port = int(os.getenv("WS_API_PORT", 8765))
        self._client = WSApiClient(host=host, port=port)
        self._connections: dict[tuple[str, str], WSConnection] = {}
        self._awaiting_input: set[tuple[str, str]] = set()
        self._register_commands()

    async def close(self) -> None:  # noqa: D401 - callback signature
        for conn in self._connections.values():
            await conn.close()
        await super().close()

    # ------------------------------------------------------------------
    # Lifecycle events
    # ------------------------------------------------------------------
    async def on_ready(self) -> None:  # noqa: D401 - callback signature
        """Log a message once the bot has connected."""

        self._log.info("Logged in as %s", self.user)

    async def on_message(
        self, message: discord.Message
    ) -> None:  # noqa: D401 - callback signature
        """Process incoming messages and stream chat replies."""

        if message.author.bot:
            return

        await self.process_commands(message)
        if message.content.startswith("!"):
            return

        user = str(message.author.id)
        session_id = str(message.channel.id)

        key = (user, session_id)
        if key in self._awaiting_input:
            conn = await self._get_connection(user, session_id, message.channel)
            try:
                await conn.send_input(message.content + "\n")
            except Exception as exc:
                self._log.error("Failed to send VM input: %s", exc)
                await message.reply(f"Error: {exc}", mention_author=False)
            finally:
                self._awaiting_input.discard(key)
            return

        docs = await self._handle_attachments(
            message.attachments,
            user=user,
            session=session_id,
        )
        if docs:
            info = "\n".join(f"{name} -> {path}" for name, path in docs)
            await message.reply(f"Uploaded:\n{info}", mention_author=False)
        conn = await self._get_connection(user, session_id, message.channel)

        if message.content.strip():
            try:
                await conn.send("team_chat", prompt=message.content)
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
            """Run ``command`` inside the user's VM and stream the output."""

            try:
                parts = []
                async for chunk in ctx.bot._client.vm_execute_stream(
                    command,
                    user=str(ctx.author.id),
                    session=str(ctx.channel.id),
                    think=False,
                    raw=True,
                ):
                    parts.append(chunk)
                output = "".join(parts).strip()
            except Exception as exc:
                await ctx.reply(f"Error: {exc}", mention_author=False)
                return

            if not output:
                output = "(no output)"
            if len(output) > 1900:
                output = output[:1900] + "..."
            await ctx.reply(f"```\n{output}\n```", mention_author=False)

        @self.command(name="run")
        async def run_cmd(ctx: commands.Context, *, command: str) -> None:
            """Execute ``command`` in the VM and return the final output."""

            try:
                output = await ctx.bot._client.vm_execute(
                    command,
                    user=str(ctx.author.id),
                    session=str(ctx.channel.id),
                    think=False,
                )
            except Exception as exc:
                await ctx.reply(f"Error: {exc}", mention_author=False)
                return

            if not output:
                output = "(no output)"
            if len(output) > 1900:
                output = output[:1900] + "..."
            await ctx.reply(f"```\n{output}\n```", mention_author=False)

        @self.command(name="ls")
        async def ls_cmd(ctx: commands.Context, path: str) -> None:
            """List directory contents in the VM."""

            try:
                rows = await ctx.bot._client.list_dir(
                    path,
                    user=str(ctx.author.id),
                    session=str(ctx.channel.id),
                    think=False,
                )
            except Exception as exc:
                await ctx.reply(f"Error: {exc}", mention_author=False)
                return

            if not rows:
                await ctx.reply("(empty)", mention_author=False)
                return

            lines = [f"{name}/" if is_dir else name for name, is_dir in rows]
            output = "\n".join(lines)
            if len(output) > 1900:
                output = output[:1900] + "..."
            await ctx.reply(f"```\n{output}\n```", mention_author=False)

        @self.command(name="read")
        async def read_cmd(ctx: commands.Context, path: str) -> None:
            """Read a file from the VM."""

            try:
                content = await ctx.bot._client.read_file(
                    path,
                    user=str(ctx.author.id),
                    session=str(ctx.channel.id),
                    think=False,
                )
            except Exception as exc:
                await ctx.reply(f"Error: {exc}", mention_author=False)
                return

            if not content:
                content = "(empty)"
            if len(content) > 1900:
                content = content[:1900] + "..."
            await ctx.reply(f"```\n{content}\n```", mention_author=False)

        @self.command(name="write")
        async def write_cmd(ctx: commands.Context, path: str, *, content: str) -> None:
            """Write ``content`` to ``path`` inside the VM."""

            try:
                result = await ctx.bot._client.write_file(
                    path,
                    content,
                    user=str(ctx.author.id),
                    session=str(ctx.channel.id),
                    think=False,
                )
            except Exception as exc:
                await ctx.reply(f"Error: {exc}", mention_author=False)
                return

            await ctx.reply(result, mention_author=False)

        @self.command(name="delete")
        async def delete_cmd(ctx: commands.Context, path: str) -> None:
            """Delete ``path`` inside the VM."""

            try:
                result = await ctx.bot._client.delete_path(
                    path,
                    user=str(ctx.author.id),
                    session=str(ctx.channel.id),
                    think=False,
                )
            except Exception as exc:
                await ctx.reply(f"Error: {exc}", mention_author=False)
                return

            await ctx.reply(result, mention_author=False)

        @self.command(name="notify")
        async def notify_cmd(ctx: commands.Context, *, message: str) -> None:
            """Send a notification to the user's VM."""

            try:
                await ctx.bot._client.send_notification(
                    message,
                    user=str(ctx.author.id),
                    session=str(ctx.channel.id),
                    think=False,
                )
            except Exception as exc:
                await ctx.reply(f"Error: {exc}", mention_author=False)
                return

            await ctx.reply("Notification sent", mention_author=False)

        @self.command(name="restartvm")
        async def restartvm_cmd(ctx: commands.Context) -> None:
            """Restart the persistent VM terminal."""

            try:
                await ctx.bot._client.restart_terminal(
                    user=str(ctx.author.id),
                    session=str(ctx.channel.id),
                    think=False,
                )
            except Exception as exc:
                await ctx.reply(f"Error: {exc}", mention_author=False)
                return

            await ctx.reply("VM terminal restarted.", mention_author=False)

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
    ) -> List[Tuple[str, str]]:
        """Download attachments and upload them to the VM.

        Audio files are transcribed locally and the transcript is uploaded as
        ``<name>_transcript.txt``. A notification is sent for every uploaded
        file so the agent can react to new documents.

        Parameters
        ----------
        attachments:
            Iterable of Discord attachments to download.
        user, session:
            WebSocket session identifiers used for file upload.
        """

        if not attachments:
            return []

        uploaded: List[Tuple[str, str]] = []
        tmpdir = Path(tempfile.mkdtemp(prefix="discord_upload_"))
        try:
            for attachment in attachments:
                dest = tmpdir / attachment.filename
                await attachment.save(dest)

                try:
                    encoded = base64.b64encode(dest.read_bytes()).decode()
                    resp = await self._client.request(
                        "upload_document",
                        user=user,
                        session=session,
                        think=False,
                        file_name=attachment.filename,
                        file_data=encoded,
                    )
                    vm_path = str(resp.get("result", ""))
                    uploaded.append((attachment.filename, vm_path))
                except Exception as exc:  # pragma: no cover - runtime errors
                    self._log.error(
                        "Upload failed for %s: %s", attachment.filename, exc
                    )
                    continue

                mime, _ = mimetypes.guess_type(attachment.filename)
                if mime and mime.startswith("audio"):
                    try:
                        text = await transcribe_audio(str(dest))
                        if text:
                            t_dest = tmpdir / f"{dest.stem}_transcript.txt"
                            t_dest.write_text(text)
                            encoded_t = base64.b64encode(t_dest.read_bytes()).decode()
                            resp = await self._client.request(
                                "upload_document",
                                user=user,
                                session=session,
                                think=False,
                                file_name=t_dest.name,
                                file_data=encoded_t,
                            )
                            t_vm_path = str(resp.get("result", ""))
                            uploaded.append((t_dest.name, t_vm_path))
                    except Exception as exc:  # pragma: no cover - runtime errors
                        self._log.error(
                            "Transcription failed for %s: %s", attachment.filename, exc
                        )
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

        return uploaded

    # ------------------------------------------------------------------
    async def _relay_messages(
        self, conn: WSConnection, channel: discord.abc.Messageable
    ) -> None:
        buffer: list[str] = []
        last_send = asyncio.get_running_loop().time()
        key = (conn.user, conn.session)
        try:
            async for msg in conn:
                file_payload = self._parse_returned_file(msg)
                if file_payload:
                    if buffer:
                        text = "".join(buffer).strip()
                        if text:
                            await channel.send(text)
                        buffer.clear()
                        last_send = asyncio.get_running_loop().time()

                    name, data = file_payload
                    await channel.send(
                        content=f"Returned file: {name}",
                        file=discord.File(BytesIO(data), filename=name),
                    )
                    continue

                prompt = self._parse_stdin_request(msg)
                if prompt is not None:
                    if buffer:
                        text = "".join(buffer).strip()
                        if text:
                            await channel.send(text)
                        buffer.clear()
                        last_send = asyncio.get_running_loop().time()
                    formatted = f"**VM input requested:** {prompt}"
                    await channel.send(formatted)
                    self._awaiting_input.add(key)
                    continue

                buffer.append(msg)
                now = asyncio.get_running_loop().time()
                if now - last_send > 0.5:
                    text = "".join(buffer).strip()
                    if text:
                        await channel.send(text)
                    buffer.clear()
                    last_send = now
        except Exception as exc:  # pragma: no cover - runtime errors
            self._log.error("WebSocket error: %s", exc)
        finally:
            if buffer:
                text = "".join(buffer).strip()
                if text:
                    await channel.send(text)

    def _parse_returned_file(self, msg: str) -> tuple[str, bytes] | None:
        """Return file name and bytes if ``msg`` encodes a returned file."""

        try:
            payload = json.loads(msg)
        except json.JSONDecodeError:
            return None
        if (
            isinstance(payload, dict)
            and "returned_file" in payload
            and "data" in payload
        ):
            name = str(payload["returned_file"])
            try:
                data = base64.b64decode(payload["data"])
            except Exception as exc:  # pragma: no cover - runtime errors
                self._log.error("Failed to decode returned file %s: %s", name, exc)
                return None
            return name, data

        if isinstance(payload, dict) and "result" in payload:
            path = Path(str(payload["result"]))
            if path.is_file():
                try:
                    data = path.read_bytes()
                except Exception as exc:  # pragma: no cover - runtime errors
                    self._log.error("Failed to read returned file %s: %s", path, exc)
                    return None
                try:
                    path.unlink()
                except Exception as exc:  # pragma: no cover - runtime errors
                    self._log.warning(
                        "Failed to delete returned file %s: %s", path, exc
                    )
                return path.name, data
        return None

    def _parse_stdin_request(self, msg: str) -> str | None:
        """Return prompt text if ``msg`` requests additional input."""

        try:
            payload = json.loads(msg)
        except json.JSONDecodeError:
            return None
        if isinstance(payload, dict) and "stdin_request" in payload:
            return str(payload["stdin_request"])
        return None

    async def _get_connection(
        self, user: str, session: str, channel: discord.abc.Messageable
    ) -> WSConnection:
        key = (user, session)
        conn = self._connections.get(key)
        if conn is None:
            conn = WSConnection(self._client, user=user, session=session, think=False)
            await conn.connect()
            self._connections[key] = conn
            asyncio.create_task(self._relay_messages(conn, channel))
        return conn


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
