from __future__ import annotations

import asyncio

from src.chat import ChatSession


async def _main() -> None:
    async with ChatSession(user="demo_user", session="demo_session") as chat:
        answer = await chat.chat(
            "Run this Python code: import math\nresult = math.factorial(5)"
        )
        print("\n>>>", answer)


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass
