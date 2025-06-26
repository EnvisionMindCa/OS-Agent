# syntax=docker/dockerfile:1

FROM python:3.11-slim AS runtime

ARG OLLAMA_MODEL=qwen3:4b
ENV OLLAMA_MODEL=${OLLAMA_MODEL}

ENV OLLAMA_KV_CACHE_TYPE=q8_0

# Install OS-level dependencies
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        build-essential \
        ffmpeg \
        curl \
        ca-certificates \
        gnupg \
        lsb-release; \
    install -m 0755 -d /etc/apt/keyrings; \
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg; \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" > /etc/apt/sources.list.d/docker.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin; \
    rm -rf /var/lib/apt/lists/*

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

EXPOSE 8765 8080 11434
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
