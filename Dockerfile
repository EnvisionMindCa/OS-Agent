# syntax=docker/dockerfile:1

FROM python:3.11-slim AS runtime

ARG OLLAMA_MODEL=qwen2.5
ENV OLLAMA_MODEL=${OLLAMA_MODEL}

ENV OLLAMA_KV_CACHE_TYPE=q8_0

# Install OS-level dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# The Ollama model is pulled at runtime by the entrypoint script. Pulling during
# build requires a running `ollama` server which isn't available in the build
# environment, leading to failures. Let the entrypoint handle the pull instead.


WORKDIR /app

# Copy dependency descriptors
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

EXPOSE 8765 11434
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
