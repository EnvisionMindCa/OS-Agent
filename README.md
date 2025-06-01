# llm-backend

This project provides a simple async interface to interact with an Ollama model and demonstrates basic tool usage. Chat histories are stored in a local SQLite database using Peewee. Histories are persisted per user and session so conversations can be resumed with context.

## Usage

```bash
python run.py
```

The script will ask the model to compute an arithmetic expression and print the answer. Conversations are automatically persisted to `chat.db` and are now associated with a user and session.
