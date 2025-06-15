from __future__ import annotations

import asyncio

import agent
from agent.vm import VMRegistry

async def _main() -> None:
    # document = await agent.upload_document("test.py", user="test_user", session="test_session")
    # print("Document uploaded:", document)
    async for resp in agent.solo_chat("run data/test.py", user="test_user", session="test_session", think=False): # or agent.team_chat()
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

from agent.utils.debug import debug_all
debug_all(globals())

