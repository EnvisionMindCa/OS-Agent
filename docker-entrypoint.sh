#!/usr/bin/env bash
set -euo pipefail

MODEL="${OLLAMA_MODEL:-qwen2.5}"
CACHE="${OLLAMA_KV_CACHE_TYPE:-q8_0}"

log() {
    echo "$(date +'%Y-%m-%dT%H:%M:%S') [entrypoint] $*" >&2
}

log "Starting Ollama service"
export OLLAMA_KV_CACHE_TYPE="${CACHE}"
ollama serve &
OLLAMA_PID=$!

wait_for_ollama() {
    for _ in {1..30}; do
        if curl -sf http://localhost:11434/api/tags >/dev/null; then
            return 0
        fi
        sleep 1
    done
    log "Ollama service failed to start" >&2
    exit 1
}

wait_for_ollama

log "Pulling Ollama model: ${MODEL}"
ollama pull "${MODEL}"

cleanup() {
    log "Shutting down..."
    kill "${OLLAMA_PID}"
    if [[ -n "${HTTP_PID:-}" ]]; then
        kill "${HTTP_PID}" || true
    fi
}
trap cleanup EXIT SIGINT SIGTERM

log "Starting static file server"
python -m agent.static_server --port "${FRONTEND_PORT:-8080}" &
HTTP_PID=$!

log "Starting OS-Agent server"
python -m agent

