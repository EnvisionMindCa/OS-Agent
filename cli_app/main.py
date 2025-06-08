from __future__ import annotations

import asyncio
from typing import AsyncIterator, List, Dict

import httpx
import typer
from colorama import Fore, Style, init

API_URL = "http://localhost:8000"

app = typer.Typer(add_completion=False, help="Chat with the LLM backend API")


async def _get_sessions_info(user: str, server: str) -> List[Dict[str, str]]:
    async with httpx.AsyncClient(base_url=server) as client:
        resp = await client.get(f"/sessions/{user}/info")
        if resp.status_code == 404:
            # Fallback to basic list for older API versions
            resp = await client.get(f"/sessions/{user}")
            resp.raise_for_status()
            names = resp.json().get("sessions", [])
            return [{"name": n, "last_message": ""} for n in names]
        resp.raise_for_status()
        return resp.json().get("sessions", [])


async def _stream_chat(
    user: str, session: str, prompt: str, server: str
) -> AsyncIterator[str]:
    async with httpx.AsyncClient(base_url=server, timeout=None) as client:
        async with client.stream(
            "POST",
            "/chat/stream",
            json={"user": user, "session": session, "prompt": prompt},
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line:
                    yield line


async def _chat_loop(user: str, server: str) -> None:
    init(autoreset=True)
    sessions = await _get_sessions_info(user, server)
    session = "default"
    if sessions:
        typer.echo("Existing sessions:")
        for idx, info in enumerate(sessions, 1):
            snippet = f" - {info['last_message'][:40]}" if info.get("last_message") else ""
            typer.echo(f"  {idx}. {info['name']}{snippet}")
        choice = typer.prompt(
            "Select session number or enter new name", default=str(len(sessions))
        )
        if choice.isdigit() and 1 <= int(choice) <= len(sessions):
            session = sessions[int(choice) - 1]["name"]
        else:
            session = choice.strip() or session
    else:
        session = typer.prompt("Session name", default=session)

    typer.echo(
        f"Chatting as {Fore.GREEN}{user}{Style.RESET_ALL} in session '{session}'"
    )

    while True:
        try:
            msg = typer.prompt(f"{Fore.CYAN}You{Style.RESET_ALL}")
        except EOFError:
            break
        if msg.strip().lower() in {"exit", "quit"}:
            break
        async for part in _stream_chat(user, session, msg, server):
            typer.echo(f"{Fore.YELLOW}{part}{Style.RESET_ALL}")


@app.callback(invoke_without_command=True)
def main(
    user: str = typer.Option("default", "--user", "-u"),
    server: str = typer.Option(API_URL, "--server", "-s"),
) -> None:
    """Start an interactive chat session."""

    asyncio.run(_chat_loop(user, server))


if __name__ == "__main__":  # pragma: no cover - manual execution
    app()
