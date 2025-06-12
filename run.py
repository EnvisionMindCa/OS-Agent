from __future__ import annotations

import asyncio

import argparse

from agent.team import TeamChatSession
from agent.solo import SoloChatSession
from agent.vm import VMRegistry


async def _main(mode: str) -> None:
    session_cls = TeamChatSession if mode == "team" else SoloChatSession
    async with session_cls(user="demo_user", session="demo_session", think=False) as chat:
        # doc_path = chat.upload_document("requirements.txt")
        # print("Document uploaded to:", doc_path)
        # async for resp in chat.chat_stream("ask how junior agent is doing"):
        # async for resp in chat.chat_stream("run hello.py"):
        # async for resp in chat.chat_stream("what is the current date?"):
        async for resp in chat.chat_stream("what is in requirements.txt"):
            print("\n>>>", resp)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the llmOS agent")
    parser.add_argument(
        "--mode",
        choices=["team", "solo"],
        default="team",
        help="Select agent mode",
    )
    args = parser.parse_args()
    asyncio.run(_main(args.mode))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        VMRegistry.shutdown_all()
