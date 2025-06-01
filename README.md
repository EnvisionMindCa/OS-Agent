# llm-backend

This project provides a simple async interface to interact with an Ollama model
and demonstrates basic tool usage. Chat histories are stored in a local SQLite
database using Peewee. Histories are persisted per user and session so
conversations can be resumed with context. One example tool is included:

* **execute_terminal** – Executes a shell command in a Linux VM with network
  access. Output from ``stdout`` and ``stderr`` is captured and returned.

The application now injects a system prompt that instructs the model to chain
multiple tools when required. This prompt ensures the assistant can orchestrate
tool calls in sequence to satisfy the user's request.

## Usage

```bash
python run.py
```

The script will instruct the model to run a simple shell command and print the result. Conversations are automatically persisted to `chat.db` and are now associated with a user and session.

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
