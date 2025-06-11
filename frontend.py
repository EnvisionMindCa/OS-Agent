"""Gradio UI for llm-backend."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Iterator, List, Optional
import typing

import gradio as gr
from huggingface_hub import HfApi, login

from src.config import UPLOAD_DIR
from src.db import list_sessions_info, reset_history
from src.team import TeamChatSession


# ---------------------------------------------------------------------------
# Authentication helpers
# ---------------------------------------------------------------------------

def hf_login(token: str) -> str:
    """Login to HuggingFace and return the username."""
    login(token=token, new_session=True)
    info = HfApi().whoami(token=token)
    return info.get("name") or info.get("email")


def get_env_token() -> str | None:
    """Return an available HuggingFace token from environment variables."""
    for name in (
        "HF_TOKEN",
        "HF_SPACE_TOKEN",
        "HF_API_TOKEN",
        "HF_ACCESS_TOKEN",
    ):
        if token := os.getenv(name):
            return token
    return None


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def _vm_host_path(user: str, vm_path: str) -> Path:
    rel = Path(vm_path).relative_to("/data")
    base = Path(UPLOAD_DIR) / user
    target = (base / rel).resolve()
    if not str(target).startswith(str(base)):
        raise ValueError("Invalid path")
    return target


def list_directory(user: str, path: str) -> list[dict[str, str | bool]]:
    target = _vm_host_path(user, path)
    if not target.exists() or not target.is_dir():
        raise FileNotFoundError(path)
    entries: list[dict[str, str | bool]] = []
    for entry in sorted(target.iterdir()):
        entries.append({"name": entry.name, "is_dir": entry.is_dir()})
    return entries


def read_file(user: str, path: str) -> str:
    target = _vm_host_path(user, path)
    if not target.exists() or target.is_dir():
        raise FileNotFoundError(path)
    return target.read_text()


def write_file(user: str, path: str, content: str) -> None:
    target = _vm_host_path(user, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)


def delete_path(user: str, path: str) -> None:
    target = _vm_host_path(user, path)
    if target.is_dir():
        for child in target.iterdir():
            if child.is_file():
                child.unlink()
            else:
                delete_path(user, str(Path("/data") / child.relative_to(target)))
        target.rmdir()
    elif target.exists():
        target.unlink()


# ---------------------------------------------------------------------------
# Chat helpers
# ---------------------------------------------------------------------------

async def chat_generator(user: str, session: str, prompt: str) -> Iterator[List[List[str]]]:
    history: List[List[str]] = []
    async with TeamChatSession(user=user, session=session) as chat:
        history.append([prompt, ""])
        resp = ""
        async for part in chat.chat_stream(prompt):
            resp += part
            history[-1][1] = resp
            yield history


# ---------------------------------------------------------------------------
# Gradio callbacks
# ---------------------------------------------------------------------------

async def send_message(user: str, session: str, message: str, history: list[list[str]] | None) -> typing.Iterator[tuple[list[list[str]], str]]:
    history = history or []
    async with TeamChatSession(user=user, session=session) as chat:
        history.append([message, ""])
        resp = ""
        async for part in chat.chat_stream(message):
            resp += part
            history[-1][1] = resp
            yield history, ""

def load_sessions(user: str) -> list[str]:
    info = list_sessions_info(user)
    return [s["name"] for s in info]


def remove_session(user: str, session: str) -> None:
    reset_history(user, session)


# ---------------------------------------------------------------------------
# UI construction
# ---------------------------------------------------------------------------

def build_ui() -> gr.Blocks:
    token = get_env_token()
    auto_user: str | None = None
    auto_sessions: list[str] = []
    if token:
        try:
            auto_user = hf_login(token)
            auto_sessions = load_sessions(auto_user)
        except Exception as exc:  # pragma: no cover - best effort
            print(f"Automatic login failed: {exc}")

    with gr.Blocks(theme=gr.themes.Soft()) as demo:
        user_state = gr.State(auto_user or str)
        session_state = gr.State("default")
        history_state = gr.State([])

        with gr.Column(visible=auto_user is None) as login_col:
            gr.Markdown("## HuggingFace Login")
            token_box = gr.Textbox(type="password", label="HuggingFace token")
            login_btn = gr.Button("Login")
            login_status = gr.Markdown()

        with gr.Row(visible=auto_user is not None) as main_row:
            with gr.Column(scale=3):
                session_drop = gr.Dropdown(
                    label="Session",
                    interactive=True,
                    choices=auto_sessions,
                    value=auto_sessions[0] if auto_sessions else None,
                )
                new_session = gr.Textbox(label="New Session Name")
                create_btn = gr.Button("Create Session")
                chatbox = gr.Chatbot(type="messages")
                msg = gr.Textbox(label="Message")
                send_btn = gr.Button("Send")

            with gr.Column(scale=2):
                gr.Markdown("### Files")
                dir_path = gr.Textbox(value="/data", label="Path")
                refresh_btn = gr.Button("List")
                file_list = gr.Dataframe(headers=["Name", "Is Dir"], datatype=["str", "bool"], interactive=False)
                open_path = gr.Textbox(label="File Path")
                open_btn = gr.Button("Open")
                file_editor = gr.Textbox(label="Content", lines=10)
                save_btn = gr.Button("Save")
                delete_btn = gr.Button("Delete")

        def do_login(token: str):
            user = hf_login(token)
            sessions = load_sessions(user)
            return {
                user_state: user,
                session_drop: gr.update(choices=sessions),
                login_col: gr.update(visible=False),
                main_row: gr.update(visible=True),
            }

        login_btn.click(do_login, inputs=token_box, outputs=[user_state, session_drop, login_col, main_row])

        def create_session(user: str, name: str):
            if not name:
                return gr.update()
            reset_history(user, name)
            sessions = load_sessions(user)
            return gr.update(value=name, choices=sessions)

        create_btn.click(create_session, inputs=[user_state, new_session], outputs=session_drop)

        def refresh_files(user: str, path: str):
            entries = list_directory(user, path)
            data = [[e["name"], e["is_dir"]] for e in entries]
            return {file_list: gr.update(value=data), dir_path: path}

        refresh_btn.click(refresh_files, inputs=[user_state, dir_path], outputs=[file_list, dir_path])

        def open_file(user: str, path: str):
            content = read_file(user, path)
            return {file_editor: content, open_path: path}

        open_btn.click(open_file, inputs=[user_state, open_path], outputs=[file_editor, open_path])

        def save_file(user: str, path: str, content: str):
            write_file(user, path, content)
            return gr.update()

        save_btn.click(save_file, inputs=[user_state, open_path, file_editor], outputs=file_editor)

        def delete_file(user: str, path: str):
            delete_path(user, path)
            return gr.update(value="")

        delete_btn.click(delete_file, inputs=[user_state, open_path], outputs=open_path)

        send_btn.click(send_message, inputs=[user_state, session_drop, msg, history_state], outputs=[chatbox, history_state, msg])
        msg.submit(send_message, inputs=[user_state, session_drop, msg, history_state], outputs=[chatbox, history_state, msg])

    return demo


if __name__ == "__main__":
    ui = build_ui()
    ui.launch()
