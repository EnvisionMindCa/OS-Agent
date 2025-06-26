# OS-Agent

OS-Agent is a production-ready framework for autonomous assistants powered by [Ollama](https://ollama.com) language models. It offers persistent memory, a Docker-backed Linux VM for tool execution and both programmatic and WebSocket interfaces. A Discord bot implementation is provided as an example client.

## Requirements

- Python 3.10+
- Docker accessible to the current user

## Installation

```bash
pip install -r requirements.txt
```

Some Python dependencies require system libraries inside your Docker image or host.

## Quick Start

### Basic Chat

```python
import asyncio
import agent

async def main():
    async with agent.TeamChatSession(user="demo", session="quick") as chat:
        async for part in chat.chat_stream("Hello"):
            print(part)

asyncio.run(main())
```

`TeamChatSession` stores conversation history in SQLite and executes commands in a dedicated VM. The session object also exposes helpers for uploading documents, editing memory and sending notifications.

### Launch the WebSocket Server

```bash
python -m agent --host 0.0.0.0 --port 8765
```

This starts a persistent WebSocket service. `python -m agent.server` works as well for backwards compatibility.

### Example Client

```python
import asyncio
import websockets

async def chat():
    uri = "ws://localhost:8765/?user=demo&session=ws&think=true"
    async with websockets.connect(uri) as ws:
        await ws.send("Hello")
        async for msg in ws:
            print(msg)

asyncio.run(chat())
```

### Gradio Frontend

Launch a simple web UI using [Gradio](https://www.gradio.app):

```bash
python frontend/gradio_app.py
```

The interface supports chat, audio and file uploads, session switching and
downloads of files returned by the agent.

Messages can be raw strings or JSON payloads containing a `command` name with optional `args`.


### Docker Image

The Dockerfile starts the WebSocket service and an embedded Ollama instance.
The entrypoint automatically launches `ollama serve` with `OLLAMA_KV_CACHE_TYPE=q8_0` before downloading the requested model.
Build and run the container exposing ports `8765`, `8080` and `11434`:

```bash
docker build -t os-agent .
docker run -p 8765:8765 -p 8080:8080 -p 11434:11434 os-agent
```

The container also serves a static web UI on port `8080`. Open
`http://localhost:8080` after the container starts to interact with the agent
from your browser.

The Ollama model specified by `OLLAMA_MODEL` is downloaded when the container
starts. Building the image does not require the model to be present.

Environment variables allow customising the defaults:

| Variable | Description | Default |
| --- | --- | --- |
| `WS_HOST` | WebSocket bind address | `0.0.0.0` |
| `WS_PORT` | WebSocket port | `8765` |
| `DEFAULT_USER` | Default user name | `demo` |
| `DEFAULT_SESSION` | Default session name | `main` |

## WebSocket API

All endpoints share the same query parameters:

- `user` – user identifier (string)
- `session` – session id (string)
- `think` – when `true` the model reasons before answering

Payloads are JSON objects of the form `{ "command": "<name>", "args": {...} }` unless you send a plain string, which is treated as `team_chat`.

### `team_chat` / `chat`
Send a chat prompt. The server streams assistant output as text fragments.

Arguments:
- `prompt` – text prompt

### `upload_document`
Upload a file for the VM. Provide either:
- `file_path` – path on the server host, or
- `file_data` and `file_name` – base64 encoded bytes and filename
  
Binary uploads are also supported by sending a WebSocket binary frame.
Prefix the frame with a 4‑byte big‑endian header length followed by a
JSON header (containing the command and `file_name`) and the raw file
bytes. The frontend uses this format when uploading files.

Returns: `{ "result": "/data/<name>" }`.

### `list_dir`
List directory contents inside the VM.

Arguments:
- `path` – directory path

Returns: `{ "result": [[name, is_dir], ...] }`.

### `read_file`
Read a file from the VM.

Arguments:
- `path` – file path

Returns: `{ "result": "<content>" }`.

### `write_file`
Write text to a file in the VM.

Arguments:
- `path` – file path
- `content` – text content

Returns: `{ "result": "Saved" }`.

### `delete_path`
Remove a file or directory in the VM.

Arguments:
- `path` – target path

Returns: `{ "result": "Deleted" }` or "File not found".

### `download_file`
Copy a file from the VM to the host system.

Arguments:
- `path` – VM path
- `dest` – optional host directory

Returns: `{ "result": "<host path>" }`.

### `vm_execute`
Execute a shell command and return the final output.

Arguments:
- `command` – shell command
- `timeout` – optional timeout in seconds

Returns: `{ "result": "<output>" }`.

### `vm_execute_stream`
Stream stdout/stderr from a shell command.

Arguments:
- `command` – shell command
- `raw` – when `true` stream the terminal output byte-by-byte

The server streams output lines by default. When `raw` is enabled, progress bars and other terminal effects are preserved. Interactive programs may emit `{ "stdin_request": "<text>" }` when additional input is required. Clients should respond using `vm_input` or `vm_keys`.

### `vm_input`
Send additional input to the running VM shell.

Arguments:
- `data` – text to write to stdin

Returns: `{ "result": "ok" }`.

### `vm_keys`
Simulate keystrokes in the VM shell.

Arguments:
- `data` – text to type
- `delay` – optional delay between characters (seconds)

Returns: `{ "result": "ok" }`.

### `send_notification`
Queue a background notification for the current user.

Arguments:
- `message` – notification text

Returns: `{ "result": "ok" }`.

### `list_sessions`
List all saved session names for the current user.

Returns: `{ "result": ["session1", ...] }`.

### `list_sessions_info`
Retrieve session names with a snippet of the last message.

Returns: `{ "result": [{"name": "session", "last_message": "..."}] }`.

### `list_documents`
List uploaded documents for the user.

Returns: `{ "result": [{"file_path": "...", "original_name": "..."}] }`.

### `get_memory`
Return the persistent memory JSON for the user.

Returns: `{ "result": "<memory>" }`.

### `set_memory`
Replace the stored memory string.

Arguments:
- `memory` – new memory contents

Returns: `{ "result": "<memory>" }`.

### `reset_memory`
Reset memory to the default template.

Returns: `{ "result": "<memory>" }`.

### `restart_terminal`
Restart the VM shell and container for the user. The agent is notified of the
restart event.

Returns: `{ "result": "restarted" }`.

## Python API

The :mod:`agent` package mirrors the WebSocket functionality and exposes helpers such as `upload_document`, `vm_execute_stream` and `send_notification`. All helper functions are **asynchronous** and must be awaited. See `agent/__init__.py` for the full list.

## Persistent Memory

User state is stored as JSON and inserted into the system prompt each turn. Memory fields can be manipulated via the `manage_memory` tool or programmatically:

```python
import agent

agent.edit_protected_memory("demo", "api_key", "secret")
```

## Notifications

Notifications allow the VM to trigger asynchronous messages back to the agent. They can be queued without an active chat:

```python
import asyncio
import agent

asyncio.run(agent.send_notification("Report ready", user="demo"))
```

## Configuration

Environment variables control most behaviour:

| Variable | Description |
| --- | --- |
| `OLLAMA_MODEL` | Ollama model name (default `qwen2.5`) |
| `OLLAMA_HOST` | Ollama server URL |
| `OLLAMA_NUM_CTX` | Context window size |
| `OLLAMA_KV_CACHE_TYPE` | Ollama KV cache type (`q8_0` by default) |
| `UPLOAD_DIR` | Host directory for uploaded files |
| `RETURN_DIR` | Host directory for returned files |
| `DB_PATH` | SQLite database path |
| `VM_IMAGE` | Docker image used for the VM (`python:3.11-slim` by default) |
| `VM_CONTAINER_TEMPLATE` | Container name pattern (`chat-vm-{user}`) |
| `VM_STATE_DIR` | Directory for persistent VM state |
| `VM_DOCKER_HOST` | Docker host socket (optional) |
| `PERSIST_VMS` | Keep VMs running between sessions (`1` by default) |
| `HARD_TIMEOUT` | Maximum seconds a command may run |
| `LOG_LEVEL` | Logging level |
| `SECRET_KEY` | Token signing key |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token lifetime |
| `REQUIRE_AUTH` | Require authentication when non-zero |
| `MEMORY_LIMIT` | Maximum size of stored memory |
| `MAX_MINI_AGENTS` | Maximum number of helper agents |
| `NOTIFICATION_POLL_INTERVAL` | Seconds between VM notification polls |

Set these variables in your environment or a `.env` file.

## Docker VM

Each user is assigned a lightweight Docker container. Uploaded files appear under `/data` and remain on disk according to `VM_STATE_DIR`. Returned files are delivered via `/return`. Commands always run inside this container; local execution is disabled, ensuring a consistent sandbox.

## License

This project is licensed under the Apache 2.0 License. See [LICENSE](LICENSE) for details.
