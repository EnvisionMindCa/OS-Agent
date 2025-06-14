from __future__ import annotations

import asyncio

import agent
from agent.vm import VMRegistry

async def _main() -> None:
    await agent.upload_document("requirements.txt")
    user = "test_user"
    session = "test_session"
    async for event in agent.solo_chat(
        "what is in requirements.txt", user=user, session=session, think=False
    ):  # or agent.team_chat()
        if event.get("input_required"):
            user_input = input(f"{event['input_required']} ")
            await agent.send_input(user_input, user=user, session=session)
        elif event.get("tool_call"):
            print("\n[TOOL CALL]", event["tool_call"])
        elif event.get("tool_result"):
            print("\n[TOOL RESULT]", event["tool_result"])
        elif event.get("message"):
            print("\n>>>", event["message"])


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        VMRegistry.shutdown_all()
