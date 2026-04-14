# Multi-stage Dockerfile for LocalScript YAML API
# Stage 1: Build with dependencies
FROM python:3.12-slim as builder

WORKDIR /build

# Install system dependencies for protocollab (includes psutil for any optional features)
RUN apt-get -o Acquire::ForceIPv4=true update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt .
COPY third_party/protocollab ./third_party/protocollab
RUN test -d ./third_party/protocollab \
    && test -n "$(find ./third_party/protocollab -mindepth 1 -maxdepth 1 -print -quit)" \
    && (test -f ./third_party/protocollab/pyproject.toml || test -f ./third_party/protocollab/setup.py) \
    || (echo "ERROR: third_party/protocollab is missing, empty, or not an installable Python package. Ensure the protocollab submodule is initialized before running docker build (for example: git submodule update --init --recursive)." >&2 && exit 1)
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies: git for submodule, docker CLI for sandbox execution
RUN apt-get -o Acquire::ForceIPv4=true update && apt-get install -y --no-install-recommends \
    git \
    docker.io \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code and assets
COPY . .

# Ensure app directory exists and templates are accessible
RUN mkdir -p /app/templates

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default environment (can override via docker-compose)
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    OLLAMA_BASE_URL=http://ollama:11434 \
    OLLAMA_MODEL=neural-chat \
    LOG_LEVEL=INFO

# Run uvicorn
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
