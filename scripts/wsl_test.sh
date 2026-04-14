#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
export PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv_wsl}"
MODE="${1:-quick}"

if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt >/dev/null

case "$MODE" in
  quick)
    # Fast local signal: run all non-integration tests.
    pytest tests/ -q -m "not integration"
    ;;
  full)
    # Full suite: includes integration tests (they may skip if deps are not running).
    pytest tests/ -q
    ;;
  integration)
    # Only the organizer samples suite.
    pytest tests/test_all_samples.py -q
    ;;
  *)
    echo "Usage: scripts/wsl_test.sh [quick|full|integration]" >&2
    exit 2
    ;;
esac
