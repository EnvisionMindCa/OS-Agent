#!/bin/sh
set -e

# Start Ollama server in the background
ollama serve >/tmp/ollama.log 2>&1 &
OLLAMA_PID=$!

cleanup() {
  kill "$OLLAMA_PID"
}
trap cleanup EXIT

# Wait until the server is ready
for i in $(seq 1 30); do
  if curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

# Run the Discord bot
exec python -m bot.discord_bot
