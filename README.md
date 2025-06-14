# llmOS-Agent

`llmOS-Agent` provides an asynchronous chat interface built around Ollama models. It supports running shell commands in an isolated Linux VM and persists conversations in SQLite.

## This repo requires Python >= 3.10. Podman is recommended but optional.

If Podman is not available, shell commands are executed directly on the host
with reduced isolation. Installing Podman ensures commands run inside a
dedicated VM for better separation.

## Features

- **Persistent chat history** – conversations are stored in `chat.db` per user and session so they can be resumed later.
- **Tool execution** – a built-in `execute_terminal` tool runs commands inside a Podman-based VM using `podman exec -i`. Network access is enabled and both stdout and stderr are captured (up to 10,000 characters). The VM is reused across chats when `PERSIST_VMS=1` so installed packages remain available.
- **System prompts** – every request includes a system prompt that guides the assistant to plan tool usage, verify results and avoid unnecessary jargon.

## Recommended Models

Any model supported by [Ollama](https://ollama.com) with `tool` tags are compatible with this repository. I personally recommend `mistral-small3.1`, I found it to work the best with this repository.

## Environment Variables

Several settings can be customised via environment variables:

- `DB_PATH` – location of the SQLite database (default `chat.db` in the project directory).
- `LOG_LEVEL` – logging verbosity (`DEBUG`, `INFO`, etc.).
- `VM_IMAGE`, `VM_STATE_DIR` and `VM_CMD` control the Podman-based VM.

## Quick Start

```bash
python run.py
```

The script issues a sample command to the model and prints the streamed response. Uploaded files go to `uploads` and are mounted in the VM at `/data`.

### Simple API

Convenience helpers allow chatting without managing sessions directly:

```python
import asyncio
import agent

async def main():
    async for event in agent.solo_chat("Hello"):
        if event.get("message"):
            print(event["message"])

asyncio.run(main())
```

Use `agent.team_chat` the same way to utilise the senior and junior agents.

### Uploading Documents

```python
async with ChatSession(think=False) as chat:
    path = chat.upload_document("path/to/file.pdf")
    async for event in chat.chat_stream(f"Summarize {path}"):
        if event.get("message"):
            print(event["message"])

# The same can be done without managing sessions directly
path = asyncio.run(agent.upload_document("path/to/file.pdf"))
listing = asyncio.run(agent.list_dir("/data"))
print(listing)
content = asyncio.run(agent.read_file(path))
asyncio.run(agent.write_file("/data/new.txt", "Hello"))
asyncio.run(agent.delete_path("/data/new.txt"))
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

Run shell commands manually with `!exec <command>`. For example:

```text
!exec ls /data
```

## VM Configuration

The shell commands run inside a Podman container. By default the image defined by `VM_IMAGE` is used (falling back to `python:3.11-slim`). When `PERSIST_VMS=1` (default) each user keeps the same container across sessions. Set `VM_STATE_DIR` to choose where per-user data is stored on the host. Use `VM_CMD` to override the Podman binary if needed.

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
podman build -t llm-vm -f docker/Dockerfile.vm .
export VM_IMAGE=llm-vm
python run.py
```
