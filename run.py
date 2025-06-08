from __future__ import annotations

import asyncio

from src.chat import ChatSession
from src.vm import VMRegistry


async def _main() -> None:
    async with ChatSession(user="demo_user", session="demo_session") as chat:
        # doc_path = chat.upload_document("note.pdf")
        async for resp in chat.chat_stream("using python, execute a code to remind me in 30 seconds to take a break."):
            print("\n>>>", resp)


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass
    finally:
        VMRegistry.shutdown_all()
