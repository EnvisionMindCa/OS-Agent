import logging
import os
import shutil
import tempfile
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

from src.chat import ChatSession
from src.db import reset_history
from src.log import get_logger

_LOG = get_logger(__name__, level=logging.INFO)


def _create_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.messages = True
    intents.message_content = True
    return commands.Bot(command_prefix="!", intents=intents)


bot = _create_bot()


@bot.event
async def on_ready() -> None:
    _LOG.info("Logged in as %s", bot.user)


@bot.command(name="reset")
async def reset(ctx: commands.Context) -> None:
    deleted = reset_history(str(ctx.author.id), str(ctx.channel.id))
    await ctx.reply(f"Chat history cleared ({deleted} messages deleted).")


async def _handle_attachments(chat: ChatSession, message: discord.Message) -> list[tuple[str, str]]:
    if not message.attachments:
        return []

    uploaded: list[tuple[str, str]] = []
    tmpdir = Path(tempfile.mkdtemp(prefix="discord_upload_"))
    try:
        for attachment in message.attachments:
            dest = tmpdir / attachment.filename
            await attachment.save(dest)
            vm_path = chat.upload_document(str(dest))
            uploaded.append((attachment.filename, vm_path))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    return uploaded


@bot.event
async def on_message(message: discord.Message) -> None:
    if message.author.bot:
        return

    await bot.process_commands(message)
    if message.content.startswith("!"):
        return

    async with ChatSession(user=str(message.author.id), session=str(message.channel.id)) as chat:
        docs = await _handle_attachments(chat, message)
        if docs:
            info = "\n".join(f"{name} -> {path}" for name, path in docs)
            await message.reply(f"Uploaded:\n{info}", mention_author=False)

        if message.content.strip():
            try:
                reply = await chat.chat(message.content)
            except Exception as exc:  # pragma: no cover - runtime errors
                _LOG.error("Failed to process message: %s", exc)
                await message.reply(f"Error: {exc}", mention_author=False)
            else:
                await message.reply(reply, mention_author=False)


def main() -> None:
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN environment variable not set")

    bot.run(token)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:  # pragma: no cover - manual exit
        pass
