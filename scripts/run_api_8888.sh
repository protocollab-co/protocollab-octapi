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

OLLAMA_START_TIMEOUT_SECONDS="${OLLAMA_START_TIMEOUT_SECONDS:-20}"

is_ollama_ready() {
	curl -fsS "${OLLAMA_BASE_URL}/api/version" >/dev/null 2>&1
}

start_ollama_via_compose() {
	if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
		printf "Ollama CLI not found. Trying: docker compose up -d ollama\n"
		if docker compose up -d ollama >/tmp/ollama-compose.log 2>&1; then
			return 0
		fi

		# Recovery path: container may already exist with the same name but be stopped.
		if docker ps -a --format '{{.Names}}' | grep -qx 'localscript-ollama'; then
			printf "Detected existing container 'localscript-ollama'. Trying: docker start localscript-ollama\n"
			docker start localscript-ollama >/tmp/ollama-compose.log 2>&1 || return 1
			return 0
		fi

		return 1
	fi

	if command -v docker-compose >/dev/null 2>&1; then
		printf "Ollama CLI not found. Trying: docker-compose up -d ollama\n"
		if docker-compose up -d ollama >/tmp/ollama-compose.log 2>&1; then
			return 0
		fi

		if docker ps -a --format '{{.Names}}' | grep -qx 'localscript-ollama'; then
			printf "Detected existing container 'localscript-ollama'. Trying: docker start localscript-ollama\n"
			docker start localscript-ollama >/tmp/ollama-compose.log 2>&1 || return 1
			return 0
		fi

		return 1
	fi

	return 1
}

ensure_ollama_ready() {
	if is_ollama_ready; then
		return 0
	fi

	if command -v ollama >/dev/null 2>&1; then
		printf "Ollama is not reachable at %s. Starting 'ollama serve'...\n" "${OLLAMA_BASE_URL}"
		ollama serve >/tmp/ollama-serve.log 2>&1 &
	else
		if ! start_ollama_via_compose; then
			printf "ERROR: Ollama is unavailable at %s and 'ollama' CLI is not installed.\n" "${OLLAMA_BASE_URL}" >&2
			printf "Hint: install Ollama CLI or run Docker service: docker compose up -d ollama\n" >&2
			return 1
		fi
	fi

	local waited=0
	while [[ "${waited}" -lt "${OLLAMA_START_TIMEOUT_SECONDS}" ]]; do
		if is_ollama_ready; then
			printf "Ollama is ready.\n"
			return 0
		fi
		waited=$((waited + 1))
		sleep 1
	done

	printf "ERROR: Ollama failed to start within %ss.\n" "${OLLAMA_START_TIMEOUT_SECONDS}" >&2
	printf "See logs: /tmp/ollama-serve.log or /tmp/ollama-compose.log\n" >&2
	return 1
}

printf "Starting API on http://0.0.0.0:8888\n"
printf "OLLAMA_BASE_URL=%s\n" "${OLLAMA_BASE_URL}"
printf "OLLAMA_MODEL=%s\n" "${OLLAMA_MODEL}"

ensure_ollama_ready

exec uvicorn app.main:app --host 0.0.0.0 --port 8888 --log-level warning
