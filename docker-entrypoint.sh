#!/usr/bin/env bash
set -euo pipefail

MODEL="${OLLAMA_MODEL:-qwen2.5}"
CACHE="${OLLAMA_KV_CACHE_TYPE:-q8_0}"

log() {
    echo "$(date +'%Y-%m-%dT%H:%M:%S') [entrypoint] $*" >&2
}

log "Starting Docker daemon"
dockerd >/tmp/dockerd.log 2>&1 &
DOCKER_PID=$!

wait_for_docker() {
    for _ in {1..30}; do
        if docker info >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    log "Docker daemon failed to start"
    cat /tmp/dockerd.log >&2 || true
    exit 1
}

wait_for_docker

if command -v nvidia-smi >/dev/null 2>&1; then
    log "NVIDIA GPU detected, enabling GPU acceleration"
else
    log "No NVIDIA GPU detected, running Ollama in CPU mode"
fi

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
    if [[ -n "${DOCKER_PID:-}" ]]; then
        kill "${DOCKER_PID}" || true
    fi
    if [[ -n "${HTTP_PID:-}" ]]; then
        kill "${HTTP_PID}" || true
    fi
}
trap cleanup EXIT SIGINT SIGTERM

log "Starting frontend"
(cd /app/frontend && npm start -- -p "${FRONTEND_PORT:-8080}") &
HTTP_PID=$!

log "Starting OS-Agent server"
python -m agent

