# llm-backend

`llm-backend` provides an asynchronous chat interface built around Ollama models. It supports running shell commands in an isolated Linux VM and persists conversations in SQLite.

## Features

- **Persistent chat history** – conversations are stored in `chat.db` per user and session so they can be resumed later.
- **Tool execution** – a built-in `execute_terminal` tool runs commands inside a Docker-based VM. Network access is enabled and both stdout and stderr are captured (up to 10,000 characters). The VM is reused across chats when `PERSIST_VMS=1` so installed packages remain available.
- **System prompts** – every request includes a system prompt that guides the assistant to plan tool usage, verify results and avoid unnecessary jargon.

## Quick Start

```bash
python run.py
```

The script issues a sample command to the model and prints the streamed response. Uploaded files go to `uploads` and are mounted in the VM at `/data`.

### Uploading Documents

```python
async with ChatSession() as chat:
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

Example request:

```bash
curl -N -X POST http://localhost:8000/chat/stream \
     -H 'Content-Type: application/json' \
     -d '{"user":"demo","session":"default","prompt":"Hello"}'
```

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
