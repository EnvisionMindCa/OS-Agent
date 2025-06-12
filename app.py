import asyncio
import base64
import json
import shlex

import gradio as gr
from gradio.oauth import attach_oauth, OAuthToken
from huggingface_hub import HfApi

from agent.team import TeamChatSession
from agent.db import list_sessions_info

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


async def _vm_execute(user: str, session: str, command: str) -> str:
    """Execute ``command`` inside the user's VM and return output."""
    chat = await _get_chat(user, session)
    vm = getattr(chat.senior, "_vm", None)
    if vm is None:
        raise RuntimeError("VM not running")
    return await vm.execute_async(command, timeout=5)


async def send_message(
    message: str, history: list[dict] | None, session: str, token: OAuthToken
):
    user = _username(token)
    chat = await _get_chat(user, session)
    history = history or []

    # user turn
    history.append({"role": "user", "content": message})
    yield history                       # show immediately

    # stream assistant turns
    async for part in chat.chat_stream(message):
        if history[-1]["role"] == "assistant":
            history[-1]["content"] += part
        else:
            history.append({"role": "assistant", "content": part})
        yield history


def load_sessions(token: OAuthToken):
    user = _username(token)
    infos = list_sessions_info(user)
    names = [info["name"] for info in infos]
    table = [[info["name"], info["last_message"]] for info in infos]
    value = names[0] if names else "default"
    return gr.update(choices=names or ["default"], value=value), table


async def list_dir(path: str, session: str, token: OAuthToken):
    user = _username(token)
    cmd = f"ls -1ap {shlex.quote(path)}"
    output = await _vm_execute(user, session, cmd)
    if output.startswith("ls:"):
        return []

    rows = []
    for line in output.splitlines():
        line = line.strip()
        if not line or line in (".", ".."):
            continue
        is_dir = line.endswith("/")
        name = line[:-1] if is_dir else line
        rows.append([name, is_dir])
    return rows


async def read_file(path: str, session: str, token: OAuthToken):
    user = _username(token)
    cmd = f"cat {shlex.quote(path)}"
    return await _vm_execute(user, session, cmd)


async def save_file(path: str, content: str, session: str, token: OAuthToken):
    user = _username(token)
    encoded = base64.b64encode(content.encode()).decode()
    cmd = (
        f"python -c 'import base64,os; "
        f'open({json.dumps(path)}, "wb").write(base64.b64decode({json.dumps(encoded)}))\''
    )
    await _vm_execute(user, session, cmd)
    return "Saved"


async def delete_path(path: str, session: str, token: OAuthToken):
    user = _username(token)
    cmd = (
        f"bash -c 'if [ -d {shlex.quote(path)} ]; then rm -rf {shlex.quote(path)} && echo Deleted; "
        f"elif [ -e {shlex.quote(path)} ]; then rm -f {shlex.quote(path)} && echo Deleted; "
        f"else echo File not found; fi'"
    )
    return await _vm_execute(user, session, cmd)


with gr.Blocks(theme=gr.themes.Soft()) as demo:
    attach_oauth(demo.app)

    login_btn = gr.LoginButton()

    with gr.Tab("Chat"):
        session_dd = gr.Dropdown(["default"], label="Session", value="default")
        refresh = gr.Button("Refresh Sessions")
        chatbox = gr.Chatbot(type="messages")
        msg = gr.Textbox(label="Message")
        send = gr.Button("Send")
        
        gr.Markdown(
    """
This is a demo app of [llmOS](https://github.com/starsnatched/llmOS-Agent), an agent framework for building AI assistants that can interact with a Linux VM to accomplish tasks.
    """
        )

    with gr.Tab("Files"):
        dir_path = gr.Textbox(label="Directory", value="/")
        list_btn = gr.Button("List")
        table = gr.Dataframe(headers=["name", "is_dir"], datatype=["str", "bool"])
        file_path = gr.Textbox(label="File Path")
        load_btn = gr.Button("Load")
        content = gr.Code(label="Content", language=None)
        save_btn = gr.Button("Save")
        del_btn = gr.Button("Delete")

    refresh.click(load_sessions, outputs=[session_dd, table])
    send_click = send.click(
        send_message,
        inputs=[msg, chatbox, session_dd],
        outputs=chatbox,
    )
    list_btn.click(list_dir, inputs=[dir_path, session_dd], outputs=table)
    load_btn.click(read_file, inputs=[file_path, session_dd], outputs=content)
    save_btn.click(save_file, inputs=[file_path, content, session_dd], outputs=content)
    del_btn.click(delete_path, inputs=[file_path, session_dd], outputs=content)
    send_click.then(lambda: "", None, msg)


demo.queue()

if __name__ == "__main__":
    demo.launch()
