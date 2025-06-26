import asyncio
import base64
import json
import os
from pathlib import Path
from typing import Optional, Tuple
from uuid import uuid4

import gradio as gr

from bot.ws_client import WSApiClient

HOST = os.getenv("WS_API_HOST", "localhost")
PORT = int(os.getenv("WS_API_PORT", 8765))

client = WSApiClient(host=HOST, port=PORT)

RETURN_DIR = Path("frontend/returned")
RETURN_DIR.mkdir(parents=True, exist_ok=True)


def _parse_returned_file(msg: str) -> Optional[Tuple[str, bytes]]:
    try:
        payload = json.loads(msg)
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict) and "returned_file" in payload and "data" in payload:
        name = str(payload["returned_file"])
        try:
            data = base64.b64decode(payload["data"])
        except Exception:
            return None
        return name, data
    if isinstance(payload, dict) and "result" in payload:
        path = Path(str(payload["result"]))
        if path.is_file():
            data = path.read_bytes()
            try:
                path.unlink()
            except Exception:
                pass
            return path.name, data
    return None


def _save_file(name: str, data: bytes) -> Path:
    dest = RETURN_DIR / f"{uuid4()}_{name}"
    dest.write_bytes(data)
    return dest


async def _stream_chat(message: str, user: str, session: str, think: bool):
    async for part in client.team_chat_stream(
        message, user=user, session=session, think=think
    ):
        yield part


def build_interface() -> gr.Blocks:
    with gr.Blocks(title="OS-Agent Chat") as demo:
        gr.Markdown("## OS-Agent Chat Interface")
        with gr.Row():
            username = gr.Textbox(label="Username", value="demo")
            think_toggle = gr.Checkbox(value=True, label="Think")
        with gr.Row():
            session_dropdown = gr.Dropdown(label="Session", choices=["main"], value="main")
            refresh_btn = gr.Button("Refresh Sessions")
            new_session = gr.Textbox(label="New Session")
            create_btn = gr.Button("Create Session")
        chat_state = gr.State([])
        files_state = gr.State([])
        chatbot = gr.Chatbot(height=400)
        msg = gr.Textbox(label="Message", scale=7)
        send_btn = gr.Button("Send", scale=1)

        with gr.Row():
            audio = gr.Audio(label="Record / Upload Audio", type="filepath")
            send_audio = gr.Button("Upload Audio")
        with gr.Row():
            upload = gr.File(label="Upload File")
            send_file = gr.Button("Upload File")
        upload_status = gr.Markdown()
        received = gr.Files(label="Received Files")

        async def refresh_sessions(user: str):
            info = await client.list_sessions_info(user=user, session="main", think=False)
            choices = [row["name"] for row in info] or ["main"]
            return gr.Dropdown.update(choices=choices, value=choices[0])

        refresh_btn.click(refresh_sessions, username, session_dropdown)

        async def create_session_fn(name: str, user: str):
            if not name:
                return gr.Dropdown.update()
            sessions = await client.list_sessions(user=user, session="main", think=False)
            if name not in sessions:
                sessions.append(name)
            return gr.Dropdown.update(choices=sessions, value=name)

        create_btn.click(create_session_fn, [new_session, username], session_dropdown)

        async def upload_file_fn(file_path: str, user: str, session_name: str):
            if not file_path:
                return gr.Markdown.update(value="No file")
            data = Path(file_path).read_bytes()
            encoded = base64.b64encode(data).decode()
            resp = await client.request(
                "upload_document",
                user=user,
                session=session_name,
                think=False,
                file_name=Path(file_path).name,
                file_data=encoded,
            )
            vm_path = str(resp.get("result", ""))
            return gr.Markdown.update(value=f"Uploaded: {vm_path}")

        send_file.click(upload_file_fn, [upload, username, session_dropdown], upload_status)

        async def upload_audio_fn(file_path: str, user: str, session_name: str):
            if not file_path:
                return gr.Markdown.update(value="No audio")
            data = Path(file_path).read_bytes()
            encoded = base64.b64encode(data).decode()
            resp = await client.request(
                "upload_document",
                user=user,
                session=session_name,
                think=False,
                file_name=Path(file_path).name,
                file_data=encoded,
            )
            vm_path = str(resp.get("result", ""))
            return gr.Markdown.update(value=f"Uploaded: {vm_path}")

        send_audio.click(upload_audio_fn, [audio, username, session_dropdown], upload_status)

        async def respond(message: str, history: list, user: str, session_name: str, think: bool, files: list):
            history = history + [(message, "")]
            async for part in _stream_chat(message, user, session_name, think):
                file_payload = _parse_returned_file(part)
                if file_payload:
                    name, data = file_payload
                    dest = _save_file(name, data)
                    files.append(dest)
                    history[-1] = (history[-1][0], history[-1][1] + f"\nReturned file: {name}")
                    yield history, [str(f) for f in files], history, files
                else:
                    history[-1] = (history[-1][0], history[-1][1] + part)
                    yield history, [str(f) for f in files], history, files
            yield history, [str(f) for f in files], history, files

        send_btn.click(
            respond,
            [msg, chat_state, username, session_dropdown, think_toggle, files_state],
            [chatbot, received, chat_state, files_state],
        )
        msg.submit(
            respond,
            [msg, chat_state, username, session_dropdown, think_toggle, files_state],
            [chatbot, received, chat_state, files_state],
        )
        return demo

if __name__ == "__main__":
    demo = build_interface()
    demo.queue()
    demo.launch()
