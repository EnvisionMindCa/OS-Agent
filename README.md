# llm-backend

This project provides a simple async interface to interact with an Ollama model
and demonstrates basic tool usage. Chat histories are stored in a local SQLite
database using Peewee. Histories are persisted per user and session so
conversations can be resumed with context. One example tool is included:

* **execute_terminal** – Executes a shell command inside a persistent Linux VM
  with network access. Use it to read uploaded documents under ``/data``, fetch
  web content via tools like ``curl`` or run any other commands. The assistant
  must invoke this tool to search online when unsure about a response. Output
  from ``stdout`` and ``stderr`` is captured when each command finishes.
  Execution happens asynchronously so the assistant can continue responding
  while the command runs.
  The VM is created when a chat session starts and reused for all subsequent
  tool calls. When ``PERSIST_VMS`` is enabled (default), each user keeps the
  same container across multiple chat sessions and across application restarts,
  so any installed packages and filesystem changes remain available. The
  environment includes Python and ``pip`` so complex tasks can be scripted using
  Python directly inside the terminal.

Sessions share state through an in-memory registry so that only one generation
can run at a time. Messages sent while a response is being produced are
ignored unless the assistant is waiting for a tool result—in that case the
pending response is cancelled and replaced with the new request.

The application injects a robust system prompt on each request. The prompt
guides the model to plan tool usage, execute commands sequentially and
verify results before replying. When the assistant is uncertain, it is directed
to search the internet with ``execute_terminal`` before giving a final answer.
The prompt is **not** stored in the chat history but is provided at runtime so
the assistant can orchestrate tool calls in sequence to fulfil the user's
request reliably. If a user message ends with ``/think`` it simply selects an
internal reasoning mode and should be stripped from the prompt before
processing.

## Usage

```bash
python run.py
```

The script will instruct the model to run a simple shell command and print the result. Conversations are automatically persisted to `chat.db` and are now associated with a user and session.

Uploaded files are stored under the `uploads` directory and mounted inside the VM at `/data`. Call ``upload_document`` on the chat session to make a file available to the model:

```python
async with ChatSession() as chat:
    path_in_vm = chat.upload_document("path/to/file.pdf")
    async for part in chat.chat_stream(f"Summarize {path_in_vm}"):
        print(part)
```

When using the Discord bot, attach one or more text files to a message to
upload them automatically. The bot responds with the location of each document
inside the VM so they can be referenced in subsequent prompts.

## Discord Bot

Create a `.env` file with your Discord token:

```bash
DISCORD_TOKEN="your-token"
```

Then start the bot:

```bash
python -m bot.discord_bot
```

Any attachments sent to the bot are uploaded to the VM and the bot replies with
their paths so they can be used in later messages.

## VM Configuration

The Linux VM used for tool execution runs inside a Docker container. By default
it pulls the image defined by the ``VM_IMAGE`` environment variable, falling
back to ``python:3.11-slim``. This base image includes Python and ``pip`` so
packages can be installed immediately. The container has network access enabled
which allows fetching additional dependencies as needed.

When ``PERSIST_VMS`` is ``1`` (default), containers are kept around and reused
across application restarts. Each user is assigned a stable container name, so
packages installed or files created inside the VM remain available the next
time the application starts. Set ``VM_STATE_DIR`` to specify the host directory
used for per-user persistent storage mounted inside the VM at ``/state``.
Set ``PERSIST_VMS=0`` to revert to the previous behaviour where containers are
stopped once no sessions are using them.

To use a fully featured Ubuntu environment, build a custom Docker image and set
``VM_IMAGE`` to that image. An example ``docker/Dockerfile.vm`` is provided:

```Dockerfile
FROM ubuntu:22.04

# Install core utilities and Python
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

The custom VM includes typical utilities like ``sudo`` and ``curl`` so it behaves
more like a standard Ubuntu installation.
