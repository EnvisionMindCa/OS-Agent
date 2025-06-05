from __future__ import annotations

import asyncio

from src.chat import ChatSession


async def _main() -> None:
    async with ChatSession(user="demo_user", session="demo_session") as chat:
        doc_path = chat.upload_document("README.md")
        answer = await chat.chat(f"List the first three lines of {doc_path}")
        print("\n>>>", answer)


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass
