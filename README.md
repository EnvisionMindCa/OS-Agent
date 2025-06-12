# llmOS-Agent

`llmOS-Agent` provides an asynchronous chat interface built around Ollama models. It supports running shell commands in an isolated Linux VM and persists conversations in SQLite.

## Features

- **Persistent chat history** – conversations are stored in `chat.db` per user and session so they can be resumed later.
- **Tool execution** – a built-in `execute_terminal` tool runs commands inside a Docker-based VM using `docker exec -i`. Network access is enabled and both stdout and stderr are captured (up to 10,000 characters). The VM is reused across chats when `PERSIST_VMS=1` so installed packages remain available.
- **System prompts** – every request includes a system prompt that guides the assistant to plan tool usage, verify results and avoid unnecessary jargon.
- **Gradio interface** – a web UI in `gradio_app.py` lets you chat and browse the VM file system. The Files tab now allows navigating any directory inside the container.

## Environment Variables

Several settings can be customised via environment variables:

- `DB_PATH` – location of the SQLite database (default `chat.db` in the project directory).
- `LOG_LEVEL` – logging verbosity (`DEBUG`, `INFO`, etc.).
- `VM_IMAGE` and `VM_STATE_DIR` control the Docker-based VM.

## Quick Start

```bash
python run.py
```

The script issues a sample command to the model and prints the streamed response. Uploaded files go to `uploads` and are mounted in the VM at `/data`.

### Uploading Documents

```python
async with ChatSession(think=False) as chat:
    path = chat.upload_document("path/to/file.pdf")
    async for part in chat.chat_stream(f"Summarize {path}"):
        print(part)
```

## Discord Bot

1. Create a `.env` file with your bot token:

   ```bash
   DISCORD_TOKEN="your-token"
   ```
2. Start the bot:

   ```bash
   python -m bot
   ```

Attachments sent to the bot are uploaded automatically and the VM path is returned so they can be referenced in later messages.

## VM Configuration

The shell commands run inside a Docker container. By default the image defined by `VM_IMAGE` is used (falling back to `python:3.11-slim`). When `PERSIST_VMS=1` (default) each user keeps the same container across sessions. Set `VM_STATE_DIR` to choose where per-user data is stored on the host.

To build a more complete environment you can create your own image, for example using `docker/Dockerfile.vm`:

```Dockerfile
FROM ubuntu:22.04
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        sudo \
        curl \
        git \
        build-essential \
    && rm -rf /var/lib/apt/lists/*
CMD ["sleep", "infinity"]
```

Build and run with:

```bash
docker build -t llm-vm -f docker/Dockerfile.vm .
export VM_IMAGE=llm-vm
python run.py
```

## REST API

Start the API server either as a module or via `uvicorn`:

```bash
python -m api_app
# or
uvicorn api_app:app --host 0.0.0.0 --port 8000
```

### Endpoints

- `POST /chat/stream` – stream the assistant's response as plain text.
- `POST /upload` – upload a document that can be referenced in chats.
- `GET /sessions/{user}` – list available session names for a user.
- `GET /vm/{user}/list` – list files in a directory under `/data`.
- `GET /vm/{user}/file` – read a file from the VM.
- `POST /vm/{user}/file` – create or overwrite a file in the VM.
- `DELETE /vm/{user}/file` – delete a file or directory from the VM.

Example request:

```bash
curl -N -X POST http://localhost:8000/chat/stream \
     -H 'Content-Type: application/json' \
     -d '{"user":"demo","session":"default","prompt":"Hello"}'
```

### Security

Set one or more API keys in the ``API_KEYS`` environment variable. Requests must
include the ``X-API-Key`` header when keys are configured. A simple rate limit is
also enforced per key or client IP, configurable via ``RATE_LIMIT``.

## Command Line Interface

Run the interactive CLI on any platform:

```bash
python -m src.cli --user yourname
```

Existing sessions are listed and you can create new ones. Type messages to see streamed replies. Use `exit` or `Ctrl+D` to quit.

### Windows Executable

For a standalone Windows build install `pyinstaller` and run:

```bash
pyinstaller --onefile -n llm-chat cli_app/main.py
```

The resulting `llm-chat.exe` works on Windows 10/11.

## macOS GUI Application

A simple graphical client built with Tkinter lives in the `mac_gui` module. It
provides a text chat interface and supports file uploads via the REST API.

### Run the GUI

```bash
pip install -r requirements.txt
python -m mac_gui
```

Use the fields at the top of the window to configure the API URL, optional API
key, user name and session. Type a message and press **Send** to chat or click
**Upload** to select a document to upload. Responses stream into the main text
area.
