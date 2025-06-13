from __future__ import annotations

import asyncio

import argparse

import agent
from agent.vm import VMRegistry

async def _main() -> None:
    document = agent.upload_document("requirements.txt")
    async for resp in agent.solo_chat("what is in requirements.txt", user="test_user", session="test_session", think=False): # or agent.team_chat()
        print("\n>>>", resp)


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        VMRegistry.shutdown_all()
