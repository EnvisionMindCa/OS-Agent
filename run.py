from __future__ import annotations

import asyncio

from src.chat import ChatSession
from src.vm import VMRegistry


async def _main() -> None:
    async with ChatSession(user="demo_user", session="demo_session") as chat:
        doc_path = chat.upload_document("note.pdf")
        # print(f"Document uploaded to VM at: {doc_path}")
        # async for resp in chat.chat_stream("Erase the contents of test.txt and write 'Hello, World!' to it."):
        # async for resp in chat.chat_stream("Verify that the file test.txt exists and contains the text 'Hello, World!'."):
        # async for resp in chat.chat_stream("Inspect the contents of note.pdf and summarize it."):
        # async for resp in chat.chat_stream("What is the content of the document I uploaded?"):
        # async for resp in chat.chat_stream("Install necessary package(s) to read PDF files and edit them."):
        async for resp in chat.chat_stream("Look up the current weather in San Francisco."):
            print("\n>>>", resp)


if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass
    finally:
        VMRegistry.shutdown_all()
