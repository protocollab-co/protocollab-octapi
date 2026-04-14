#!/usr/bin/env bash
set -euo pipefail

# Run LocalScript API on port 8888 using local Ollama.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

export OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"
export OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5-coder:1.5b}"
export PYTHONPATH="${PYTHONPATH:-${ROOT_DIR}}"
export SANDBOX_TIMEOUT_SECONDS="${SANDBOX_TIMEOUT_SECONDS:-5}"
export SANDBOX_MEMORY_MB="${SANDBOX_MEMORY_MB:-128}"
export SANDBOX_NETWORK_MODE="${SANDBOX_NETWORK_MODE:-none}"

printf "Starting API on http://0.0.0.0:8888\n"
printf "OLLAMA_BASE_URL=%s\n" "${OLLAMA_BASE_URL}"
printf "OLLAMA_MODEL=%s\n" "${OLLAMA_MODEL}"

exec uvicorn app.main:app --host 0.0.0.0 --port 8888 --log-level warning
