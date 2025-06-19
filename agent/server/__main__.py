from __future__ import annotations

import asyncio
import argparse

from . import AgentWebSocketServer


async def _main(host: str, port: int) -> None:
    server = AgentWebSocketServer(host=host, port=port)
    await server.start()
    try:
        await asyncio.Future()  # run forever
    finally:
        await server.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run websocket server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", type=int, default=8765, help="Listen port")
    args = parser.parse_args()

    asyncio.run(_main(args.host, args.port))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
