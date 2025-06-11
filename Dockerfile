# Use official Python runtime as a parent image
FROM python:3.11-slim

# Ensure stdout/stderr logs are shown in real time
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install any system dependencies if required
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies first for better cache utilisation
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose Gradio default port (HuggingFace sets $PORT automatically)
EXPOSE 7860

# Start the Gradio application
CMD ["python", "app.py"]
