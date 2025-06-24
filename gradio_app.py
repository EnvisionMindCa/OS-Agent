import base64
import json
import os
from pathlib import Path

import gradio as gr

from bot.ws_client import WSApiClient


def _client(host: str, port: int) -> WSApiClient:
    return WSApiClient(host=host, port=int(port))


async def _chat(prompt: str, history: list, user: str, session: str, think: bool, host: str, port: int):
    history = history or []
    client = _client(host, port)
    history.append((prompt, ""))
    idx = len(history) - 1
    async for part in client.team_chat_stream(prompt, user=user, session=session, think=think):
        history[idx] = (prompt, history[idx][1] + part)
        yield history


async def _upload(file: gr.File, user: str, session: str, host: str, port: int):
    data = Path(file.name).read_bytes()
    b64 = base64.b64encode(data).decode()
    client = _client(host, port)
    resp = await client.request(
        "upload_document",
        user=user,
        session=session,
        file_data=b64,
        file_name=Path(file.name).name,
    )
    return str(resp.get("result", ""))


async def _list_dir(path: str, user: str, session: str, host: str, port: int):
    client = _client(host, port)
    items = await client.list_dir(path, user=user, session=session)
    return "\n".join(f"{n}/" if d else n for n, d in items)


async def _read_file(path: str, user: str, session: str, host: str, port: int):
    client = _client(host, port)
    return await client.read_file(path, user=user, session=session)


async def _write_file(path: str, content: str, user: str, session: str, host: str, port: int):
    client = _client(host, port)
    return await client.write_file(path, content, user=user, session=session)


async def _delete_path(path: str, user: str, session: str, host: str, port: int):
    client = _client(host, port)
    return await client.delete_path(path, user=user, session=session)


async def _download_file(path: str, dest: str, user: str, session: str, host: str, port: int):
    client = _client(host, port)
    return await client.download_file(path, dest=dest or None, user=user, session=session)


async def _vm_execute(command: str, user: str, session: str, think: bool, timeout: int, host: str, port: int):
    client = _client(host, port)
    return await client.vm_execute(command, user=user, session=session, think=think, timeout=timeout or None)


async def _vm_execute_stream(command: str, user: str, session: str, think: bool, raw: bool, host: str, port: int):
    client = _client(host, port)
    output = ""
    async for chunk in client.vm_execute_stream(command, user=user, session=session, think=think, raw=raw):
        output += chunk
        yield output


async def _vm_input(data: str, user: str, session: str, host: str, port: int):
    client = _client(host, port)
    await client.vm_send_input(data, user=user, session=session)
    return "ok"


async def _vm_keys(data: str, delay: float, user: str, session: str, host: str, port: int):
    client = _client(host, port)
    await client.vm_send_keys(data, user=user, session=session, delay=delay)
    return "ok"


async def _send_notification(message: str, user: str, session: str, host: str, port: int):
    client = _client(host, port)
    await client.send_notification(message, user=user, session=session)
    return "ok"


async def _list_sessions(user: str, session: str, host: str, port: int):
    client = _client(host, port)
    sessions = await client.list_sessions(user=user, session=session)
    return "\n".join(sessions)


async def _list_sessions_info(user: str, session: str, host: str, port: int):
    client = _client(host, port)
    info = await client.list_sessions_info(user=user, session=session)
    return json.dumps(info, indent=2)


async def _list_documents(user: str, session: str, host: str, port: int):
    client = _client(host, port)
    docs = await client.list_documents(user=user, session=session)
    return json.dumps(docs, indent=2)


async def _get_memory(user: str, session: str, host: str, port: int):
    client = _client(host, port)
    return await client.get_memory(user=user, session=session)


async def _set_memory(memory: str, user: str, session: str, host: str, port: int):
    client = _client(host, port)
    return await client.set_memory(memory, user=user, session=session)


async def _reset_memory(user: str, session: str, host: str, port: int):
    client = _client(host, port)
    return await client.reset_memory(user=user, session=session)


async def _restart_terminal(user: str, session: str, host: str, port: int):
    client = _client(host, port)
    return await client.restart_terminal(user=user, session=session)


def build_interface(
    *,
    default_host: str = "localhost",
    default_port: int = 8765,
    default_user: str = "demo",
    default_session: str = "main",
    default_think: bool = True,
) -> gr.Blocks:
    """Create the Gradio UI."""

    with gr.Blocks() as demo:
        with gr.Row():
            host = gr.Textbox(value=default_host, label="Host")
            port = gr.Number(value=default_port, label="Port")
            user = gr.Textbox(value=default_user, label="User")
            session = gr.Textbox(value=default_session, label="Session")
            think = gr.Checkbox(value=default_think, label="Think")

        with gr.Tab("Chat"):
            chatbot = gr.Chatbot()
            msg = gr.Textbox(label="Message")
            chat_btn = gr.Button("Send")
            chat_btn.click(_chat, inputs=[msg, chatbot, user, session, think, host, port], outputs=chatbot, stream=True)
            clear_btn = gr.Button("Clear")
            clear_btn.click(lambda: None, None, chatbot, queue=False)

        with gr.Tab("Files"):
            with gr.Row():
                upload_file = gr.File()
                upload_btn = gr.Button("Upload")
                upload_out = gr.Textbox(label="Uploaded Path")
                upload_btn.click(_upload, inputs=[upload_file, user, session, host, port], outputs=upload_out)
            with gr.Row():
                list_path = gr.Textbox(label="List Dir Path", value="/data")
                list_btn = gr.Button("List")
                list_out = gr.Textbox(label="Listing")
                list_btn.click(_list_dir, inputs=[list_path, user, session, host, port], outputs=list_out)
            with gr.Row():
                read_path = gr.Textbox(label="Read File Path")
                read_btn = gr.Button("Read")
                read_out = gr.Textbox(label="Content")
                read_btn.click(_read_file, inputs=[read_path, user, session, host, port], outputs=read_out)
            with gr.Row():
                write_path = gr.Textbox(label="Write File Path")
                write_content = gr.Textbox(label="Content")
                write_btn = gr.Button("Write")
                write_out = gr.Textbox(label="Result")
                write_btn.click(_write_file, inputs=[write_path, write_content, user, session, host, port], outputs=write_out)
            with gr.Row():
                del_path = gr.Textbox(label="Delete Path")
                del_btn = gr.Button("Delete")
                del_out = gr.Textbox(label="Result")
                del_btn.click(_delete_path, inputs=[del_path, user, session, host, port], outputs=del_out)
            with gr.Row():
                dl_path = gr.Textbox(label="Download Path")
                dl_dest = gr.Textbox(label="Dest", value="")
                dl_btn = gr.Button("Download")
                dl_out = gr.Textbox(label="Result")
                dl_btn.click(_download_file, inputs=[dl_path, dl_dest, user, session, host, port], outputs=dl_out)

        with gr.Tab("Terminal"):
            cmd = gr.Textbox(label="Command")
            timeout_box = gr.Number(value=None, label="Timeout (s)")
            term_btn = gr.Button("Run")
            term_out = gr.Textbox(label="Output")
            term_btn.click(
                _vm_execute,
                inputs=[cmd, user, session, think, timeout_box, host, port],
                outputs=term_out,
            )

            cmd_stream = gr.Textbox(label="Stream Command")
            raw_chk = gr.Checkbox(value=False, label="Raw")
            stream_btn = gr.Button("Stream")
            stream_out = gr.Textbox(label="Stream Output")
            stream_btn.click(
                _vm_execute_stream,
                inputs=[cmd_stream, user, session, think, raw_chk, host, port],
                outputs=stream_out,
                stream=True,
            )
            in_data = gr.Textbox(label="Send Input")
            in_btn = gr.Button("Send")
            in_out = gr.Textbox(label="Result")
            in_btn.click(_vm_input, inputs=[in_data, user, session, host, port], outputs=in_out)
            keys_data = gr.Textbox(label="Send Keys")
            keys_delay = gr.Number(value=0.05, label="Delay")
            keys_btn = gr.Button("Type")
            keys_out = gr.Textbox(label="Result")
            keys_btn.click(_vm_keys, inputs=[keys_data, keys_delay, user, session, host, port], outputs=keys_out)

        with gr.Tab("Memory"):
            mem_get_btn = gr.Button("Get Memory")
            mem_text = gr.Textbox(label="Memory", lines=10)
            mem_get_btn.click(_get_memory, inputs=[user, session, host, port], outputs=mem_text)
            mem_set = gr.Textbox(label="New Memory", lines=10)
            mem_set_btn = gr.Button("Set Memory")
            mem_set_btn.click(_set_memory, inputs=[mem_set, user, session, host, port], outputs=mem_text)
            mem_reset_btn = gr.Button("Reset Memory")
            mem_reset_btn.click(_reset_memory, inputs=[user, session, host, port], outputs=mem_text)

        with gr.Tab("Sessions"):
            sess_list_btn = gr.Button("List Sessions")
            sess_list_out = gr.Textbox(label="Sessions")
            sess_list_btn.click(_list_sessions, inputs=[user, session, host, port], outputs=sess_list_out)
            sess_info_btn = gr.Button("List Session Info")
            sess_info_out = gr.Textbox(label="Info")
            sess_info_btn.click(_list_sessions_info, inputs=[user, session, host, port], outputs=sess_info_out)
            docs_btn = gr.Button("List Documents")
            docs_out = gr.Textbox(label="Documents")
            docs_btn.click(_list_documents, inputs=[user, session, host, port], outputs=docs_out)

        with gr.Tab("Admin"):
            note_text = gr.Textbox(label="Notification")
            note_btn = gr.Button("Send")
            note_out = gr.Textbox(label="Result")
            note_btn.click(_send_notification, inputs=[note_text, user, session, host, port], outputs=note_out)
            restart_btn = gr.Button("Restart Terminal")
            restart_out = gr.Textbox(label="Result")
            restart_btn.click(_restart_terminal, inputs=[user, session, host, port], outputs=restart_out)
    return demo


def main() -> None:
    """Launch the Gradio interface with environment defaults."""

    demo = build_interface(
        default_host=os.environ.get("WS_HOST", "localhost"),
        default_port=int(os.environ.get("WS_PORT", "8765")),
        default_user=os.environ.get("DEFAULT_USER", "demo"),
        default_session=os.environ.get("DEFAULT_SESSION", "main"),
    )
    demo.queue()
    demo.launch()


if __name__ == "__main__":
    main()
