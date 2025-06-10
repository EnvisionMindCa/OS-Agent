from __future__ import annotations

import asyncio

from src.team import TeamChatSession
from src.vm import VMRegistry


async def _main() -> None:
    async with TeamChatSession(user="demo_user", session="demo_session") as chat:
        # doc_path = chat.upload_document("requirements.txt")
        # print("Document uploaded to:", doc_path)
        # async for resp in chat.chat_stream("ask how junior agent is doing"):
        # async for resp in chat.chat_stream("run hello.py"):
        async for resp in chat.chat_stream("what is in requirements.txt"):
            print("\n>>>", resp)


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass
    finally:
        VMRegistry.shutdown_all()
