# syntax=docker/dockerfile:1

FROM python:3.10-slim as base

# Install system dependencies and Ollama
RUN apt-get update && \
    apt-get install -y curl gnupg && \
    rm -rf /var/lib/apt/lists/* && \
    curl -fsSL https://ollama.com/install.sh | sh

# Create non-root user
RUN useradd --create-home --uid 1000 botuser

WORKDIR /app

# Pull models at build time
ENV OLLAMA_MODEL="qwen3"
ENV OLLAMA_EMBEDDING_MODEL="nomic-embed-text"
RUN ollama pull "$OLLAMA_MODEL" && ollama pull "$OLLAMA_EMBEDDING_MODEL"

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Entrypoint script manages Ollama and the bot
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER botuser
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["/entrypoint.sh"]
