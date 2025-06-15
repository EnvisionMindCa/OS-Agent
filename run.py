from __future__ import annotations

import asyncio

import agent
from agent.vm import VMRegistry

async def _main() -> None:
    # document = await agent.upload_document("test.py", user="test_user", session="test_session")
    # print("Document uploaded:", document)
    async for part in agent.solo_chat("run data/test.py", user="test_user", session="test_session", think=False):
        if part.get("tool_call"):
            tc = part["tool_call"]
            print(f"[tool] {tc['name']} {tc['arguments']}")
        if msg := part.get("message"):
            if part.get("role") == "tool":
                name = part.get("tool_name", "tool")
                print(f"[{name}] {msg}")
            else:
                print(msg)


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

