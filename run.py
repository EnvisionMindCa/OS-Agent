from __future__ import annotations

import asyncio

import agent
from agent.vm import VMRegistry

async def _main() -> None:
    import datetime
    # document = await agent.upload_document("test.py", user="test_user", session="test_session")
    # print("Document uploaded:", document)
    agent.edit_protected_memory("test_user", ".env", "TEST_VAR=12345")
    async for resp in agent.solo_chat("what's in the protected memory of yours?", user="test_user", session="test_session", think=False, extra={"time": datetime.datetime.now()}): # or agent.team_chat()
        print("\n>>>", resp)
        
    # or using speech:
    # async for resp in agent.solo_chat(agent.transcribe_audio("path/to/audio/file.wav"), user="test_user", session="test_session", think=False):
    #     print("\n>>>", resp)


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        VMRegistry.shutdown_all()

from agent.utils.debug import debug_all
debug_all(globals())
