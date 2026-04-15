#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
	exec docker compose up --build "$@"
fi

if command -v docker-compose >/dev/null 2>&1; then
	exec docker-compose up --build "$@"
fi

printf "ERROR: Neither 'docker compose' nor 'docker-compose' is available.\n" >&2
exit 1