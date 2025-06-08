from __future__ import annotations

"""Standalone demo script using the team-of-agents workflow."""

import asyncio

from src.team import TeamChatSession
from src.vm import VMRegistry


async def _demo(prompt: str) -> None:
    """Run a single prompt through the full agent team."""

    async with TeamChatSession(user="demo_user", session="demo_session") as team:
        async for resp in team.chat_stream(prompt):
            print("\n>>>", resp)


def main() -> None:
    """Entry point for the demo script."""

    prompt = (
        "using python, execute a code to remind me in 30 seconds to take a break."
    )

    try:
        asyncio.run(_demo(prompt))
    except KeyboardInterrupt:
        pass
    finally:
        VMRegistry.shutdown_all()


if __name__ == "__main__":
    main()
