from __future__ import annotations

import asyncio

from src.team import TeamChatSession
from src.vm import VMRegistry


async def _main() -> None:
    async with TeamChatSession(user="demo_user", session="demo_session") as chat:
        # doc_path = chat.upload_document("note.pdf")
        async for resp in chat.chat_stream("ask how junior agent is doing"):
            print("\n>>>", resp)


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass
    finally:
        VMRegistry.shutdown_all()
