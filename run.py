from __future__ import annotations

import asyncio
import argparse

import agent
from agent.vm import VMRegistry
from agent.db import authenticate_user, register_user, db
from agent.config import DEFAULT_CONFIG
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def ensure_user(username: str, password: str | None = None) -> None:
    """Ensure ``username`` exists; verify or create with ``password`` if required."""

    if not DEFAULT_CONFIG.require_auth:
        db.get_or_create_user(username)
        return

    if password is None:
        raise ValueError("Password required when authentication is enabled")

    user = authenticate_user(username)
    if user:
        if not pwd_context.verify(password, user.password_hash):
            raise ValueError("Incorrect password for existing user")
        return
    hashed = pwd_context.hash(password)
    register_user(username, hashed)


async def _main(username: str, session: str) -> None:
    import datetime
    # document = await agent.upload_document("test.py", user="test_user", session="test_session")
    # print("Document uploaded:", document)
    # agent.edit_protected_memory("test_user", ".env", "TEST_VAR=12345")
    # async for resp in agent.solo_chat(
    #     "what's in the protected memory of yours?",
    #     user="test_user",
    #     session="test_session",
    #     think=False,
    #     extra={"time": datetime.datetime.now()},
    # ):
    #     print("\nSOLO >>", resp)

    # ensure_user(username, password)

    async with agent.TeamChatSession(user=username, session=session, think=False) as chat:
        await chat.send_notification("Session started")
        async for part in chat.chat_stream(
            "solve cancer. do not come back until you have a solution.",
        ):
            print("\nTEAM >>", part)
        await chat.send_notification("Session finished")

    # This notification will be delivered the next time the user starts a session
    agent.send_notification("Background job completed", user=username)
        
    # or using speech:
    # async for resp in agent.solo_chat(agent.transcribe_audio("path/to/audio/file.wav"), user="test_user", session="test_session", think=False):
    #     print("\n>>>", resp)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sample chat with authentication")
    parser.add_argument("--user", default="test_user", help="Username")
    parser.add_argument("--session", default="test_session", help="Session name")
    args = parser.parse_args()

    asyncio.run(_main(args.user, args.session))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        VMRegistry.shutdown_all()

from agent.utils.debug import debug_all
debug_all(globals())
