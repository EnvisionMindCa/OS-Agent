from __future__ import annotations

import asyncio
import argparse

import agent
from dataclasses import replace
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


async def _main(username: str, session: str, cfg) -> None:
    import datetime
    # document = await agent.upload_document("test.py", user="test_user", session="test_session")
    # print("Document uploaded:", document)
    # agent.edit_protected_memory("test_user", ".env", "TEST_VAR=12345")

    # ensure_user(username, password)

    async with agent.TeamChatSession(user=username, session=session, think=False, config=cfg) as chat:
        # dir = chat.upload_document("test.txt")
        
        # async for resp in chat.send_notification_stream(f"Uploaded to {dir}"):
        #     print("TEAM >>", resp)
        async for part in chat.chat_stream(
            "return the /data/test.txt file",
        ):
            print("\nTEAM >>", part)
        # await chat.send_notification("Session finished")

    # This notification will be delivered the next time the user starts a session
    # agent.send_notification("Background job completed", user=username)
        


def main() -> None:
    parser = argparse.ArgumentParser(description="Sample chat with authentication")
    parser.add_argument("--user", default="test_user", help="Username")
    parser.add_argument("--session", default="test_session", help="Session name")
    parser.add_argument("--vm-image", help="Docker image for the VM")
    parser.add_argument(
        "--vm-container-template",
        help="Format string for container names",
    )
    args = parser.parse_args()

    cfg = DEFAULT_CONFIG
    if args.vm_image:
        cfg = replace(cfg, vm_image=args.vm_image)
    if args.vm_container_template:
        cfg = replace(cfg, vm_container_template=args.vm_container_template)

    asyncio.run(_main(args.user, args.session, cfg))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    finally:
        VMRegistry.shutdown_all()

from agent.utils.debug import debug_all
debug_all(globals())
