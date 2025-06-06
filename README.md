# llm-backend

This project provides a simple async interface to interact with an Ollama model
and demonstrates basic tool usage. Chat histories are stored in a local SQLite
database using Peewee. Histories are persisted per user and session so
conversations can be resumed with context. One example tool is included:

* **execute_terminal** – Executes a shell command inside a persistent Linux VM
  with network access. Use it to read uploaded documents under ``/data`` or run
  other commands. Output from ``stdout`` and ``stderr`` is captured and
  returned. The VM is created when a chat session starts and reused for all
  subsequent tool calls.

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
    reply = await chat.chat(f"Summarize {path_in_vm}")
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
