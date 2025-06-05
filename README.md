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

The application now injects a system prompt that instructs the model to chain
multiple tools when required. This prompt ensures the assistant can orchestrate
tool calls in sequence to satisfy the user's request.

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

## Docker

A Dockerfile is provided to run the Discord bot along with an Ollama server. The image installs Ollama, pulls the LLM and embedding models, and starts both the server and the bot.

Build the image:

```bash
docker build -t llm-discord-bot .
```

Run the container:

```bash
docker run -e DISCORD_TOKEN=your-token llm-discord-bot
```

The environment variables `OLLAMA_MODEL` and `OLLAMA_EMBEDDING_MODEL` can be set at build or run time to specify which models to download.
