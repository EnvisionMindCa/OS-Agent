from __future__ import annotations

import asyncio

import argparse

import agent
from agent.vm import VMRegistry

async def _main(mode: str) -> None:
    async for resp in agent.solo_chat("what is in requirements.txt", user="test_user", session="test_session", think=False): # or agent.team_chat()
        print("\n>>>", resp)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the llmOS agent")
    parser.add_argument(
        "--mode",
        choices=["team", "solo"],
        default="team",
        help="Select agent mode",
    )
    args = parser.parse_args()
    asyncio.run(_main(args.mode))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        VMRegistry.shutdown_all()
