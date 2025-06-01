from __future__ import annotations

import asyncio

from src.chat import ChatSession


async def _main() -> None:
    chat = ChatSession()
    answer = await chat.chat("What is 10 + 23?")
    print("\n>>>", answer)


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass
