import asyncio
import shutil
from pathlib import Path

import gradio as gr
from gradio.oauth import attach_oauth, OAuthToken
from huggingface_hub import HfApi

from src.team import TeamChatSession
from src.db import list_sessions_info
from src.config import UPLOAD_DIR

# Store active chat sessions
_SESSIONS: dict[tuple[str, str], TeamChatSession] = {}
_API = HfApi()


def _username(token: OAuthToken) -> str:
    """Return the username for the given token."""
    info = _API.whoami(token.token)
    return info.get("name") or info.get("user", "unknown")


async def _get_chat(user: str, session: str) -> TeamChatSession:
    """Return an active :class:`TeamChatSession` for ``user`` and ``session``."""
    key = (user, session)
    chat = _SESSIONS.get(key)
    if chat is None:
        chat = TeamChatSession(user=user, session=session)
        await chat.__aenter__()
        _SESSIONS[key] = chat
    return chat


def _vm_host_path(user: str, vm_path: str) -> Path:
    rel = Path(vm_path).relative_to("/data")
    base = (Path(UPLOAD_DIR) / user).resolve()
    target = (base / rel).resolve()
    if not target.is_relative_to(base):
        raise ValueError("Invalid path")
    return target


async def send_message(message: str, history: list[tuple[str, str]], session: str, token: OAuthToken):
    user = _username(token)
    chat = await _get_chat(user, session)
    history = history or []
    history.append((message, ""))
    async for part in chat.chat_stream(message):
        history[-1] = (message, history[-1][1] + part)
        yield history


def load_sessions(token: OAuthToken):
    user = _username(token)
    infos = list_sessions_info(user)
    names = [info["name"] for info in infos]
    table = [[info["name"], info["last_message"]] for info in infos]
    value = names[0] if names else "default"
    return gr.update(choices=names or ["default"], value=value), table


def list_dir(path: str, token: OAuthToken):
    user = _username(token)
    target = _vm_host_path(user, path)
    if not target.exists() or not target.is_dir():
        return []
    entries = []
    for entry in sorted(target.iterdir()):
        entries.append({"name": entry.name, "is_dir": entry.is_dir()})
    return entries


def read_file(path: str, token: OAuthToken):
    user = _username(token)
    target = _vm_host_path(user, path)
    if not target.exists():
        return "File not found"
    if target.is_dir():
        return "Path is a directory"
    try:
        return target.read_text()
    except UnicodeDecodeError:
        return "Binary file not supported"


def save_file(path: str, content: str, token: OAuthToken):
    user = _username(token)
    target = _vm_host_path(user, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return "Saved"


def delete_path(path: str, token: OAuthToken):
    user = _username(token)
    target = _vm_host_path(user, path)
    if target.is_dir():
        shutil.rmtree(target)
    elif target.exists():
        target.unlink()
    else:
        return "File not found"
    return "Deleted"


with gr.Blocks(theme=gr.themes.Soft()) as demo:
    attach_oauth(demo.app)

    login_btn = gr.LoginButton()

    with gr.Tab("Chat"):
        session_dd = gr.Dropdown(["default"], label="Session", value="default")
        refresh = gr.Button("Refresh Sessions")
        chatbox = gr.Chatbot()
        msg = gr.Textbox(label="Message")
        send = gr.Button("Send")

    with gr.Tab("Files"):
        dir_path = gr.Textbox(label="Directory", value="/data")
        list_btn = gr.Button("List")
        table = gr.Dataframe(headers=["name", "is_dir"], datatype=["str", "bool"])
        file_path = gr.Textbox(label="File Path")
        load_btn = gr.Button("Load")
        content = gr.Code(label="Content", language="text")
        save_btn = gr.Button("Save")
        del_btn = gr.Button("Delete")

    refresh.click(load_sessions, outputs=[session_dd, table])
    send.click(send_message, inputs=[msg, chatbox, session_dd], outputs=chatbox)
    list_btn.click(list_dir, inputs=dir_path, outputs=table)
    load_btn.click(read_file, inputs=file_path, outputs=content)
    save_btn.click(save_file, inputs=[file_path, content], outputs=content)
    del_btn.click(delete_path, inputs=file_path, outputs=content)
    send.then(lambda: "", None, msg)


demo.queue()

if __name__ == "__main__":
    demo.launch()
