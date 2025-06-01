# llm-backend

This project provides a simple async interface to interact with an Ollama model
and demonstrates basic tool usage. Chat histories are stored in a local SQLite
database using Peewee. Histories are persisted per user and session so
conversations can be resumed with context. Two example tools are included:

* **add_two_numbers** – Adds two integers.
* **execute_python** – Executes Python code in a sandbox with selected built-ins
  and allows importing safe modules like ``math``. The result is returned from a
  ``result`` variable or captured output.

The application now injects a system prompt that instructs the model to chain
multiple tools when required. This prompt ensures the assistant can orchestrate
tool calls in sequence to satisfy the user's request.

## Usage

```bash
python run.py
```

The script will ask the model to compute an arithmetic expression and print the answer. Conversations are automatically persisted to `chat.db` and are now associated with a user and session.
