from __future__ import annotations

import asyncio

from src.chat import ChatSession


async def _main() -> None:
    async with ChatSession(user="demo_user", session="demo_session") as chat:
        doc_path = chat.upload_document("test.txt")
        # print(f"Document uploaded to VM at: {doc_path}")
        # answer = await chat.chat(f"Remove all contents of test.txt and add the text 'Hello, World!' to it.")
        answer = await chat.chat("What is in /data directory?")
        print("\n>>>", answer)


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass
