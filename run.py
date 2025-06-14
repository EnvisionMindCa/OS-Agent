from __future__ import annotations

import asyncio

import agent
from agent.vm import VMRegistry

async def _main() -> None:
    await agent.upload_document("requirements.txt")
    user = "test_user"
    session = "test_session"
    async for resp in agent.solo_chat(
        "what is in requirements.txt", user=user, session=session, think=False
    ):  # or agent.team_chat()
        if resp.startswith("[INPUT REQUIRED]"):
            prompt = resp.removeprefix("[INPUT REQUIRED]").strip()
            user_input = input(f"{prompt} ")
            await agent.send_input(user_input, user=user, session=session)
        else:
            print("\n>>>", resp)


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        VMRegistry.shutdown_all()
