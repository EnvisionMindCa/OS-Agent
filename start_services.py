import asyncio
import os

from agent.server.__main__ import _main as run_server
from gradio_app import build_interface


async def main() -> None:
    ws_host = os.environ.get("WS_HOST", "0.0.0.0")
    ws_port = int(os.environ.get("WS_PORT", "8765"))
    ui_host = os.environ.get("UI_HOST", "0.0.0.0")
    ui_port = int(os.environ.get("UI_PORT", "7860"))
    user = os.environ.get("DEFAULT_USER", "demo")
    session = os.environ.get("DEFAULT_SESSION", "main")

    server_task = asyncio.create_task(run_server(ws_host, ws_port))

    interface = build_interface(
        default_host=ws_host,
        default_port=ws_port,
        default_user=user,
        default_session=session,
    )
    interface.queue()
    app = interface.launch(
        server_name=ui_host,
        server_port=ui_port,
        prevent_thread_lock=True,
    )

    try:
        await server_task
    except asyncio.CancelledError:
        pass
    finally:
        app.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
