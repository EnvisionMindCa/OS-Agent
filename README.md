# llm-backend

This project provides a simple async interface to interact with an Ollama model
and demonstrates basic tool usage. Chat histories are stored in a local SQLite
database using Peewee. Histories are persisted per user and session so
conversations can be resumed with context. One example tool is included:

* **execute_terminal** – Executes a shell command inside a persistent Linux VM
  with network access. Use it to read uploaded documents under ``/data`` or run
  other commands. Output from ``stdout`` and ``stderr`` is captured and
  returned. Commands run asynchronously so the assistant can continue
  responding while they execute. The VM is created when a chat session starts
  and reused for all subsequent tool calls.

Sessions share state through an in-memory registry so that only one generation
can run at a time. Messages sent while a response is being produced are
ignored unless the assistant is waiting for a tool result—in that case the
pending response is cancelled and replaced with the new request.

The application injects a robust system prompt on each request. The prompt
guides the model to plan tool usage, execute commands sequentially and
verify results before replying. It is **not** stored in the chat history but is
provided at runtime so the assistant can orchestrate tool calls in sequence to
fulfil the user's request reliably.

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
