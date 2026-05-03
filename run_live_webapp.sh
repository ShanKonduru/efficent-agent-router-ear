#!/usr/bin/env bash
set -euo pipefail

VENV=".venv/bin/activate"

if [[ ! -f "$VENV" ]]; then
    echo "[ERROR] Virtual environment not found."
    echo "        Run: python -m venv .venv && .venv/bin/pip install -e '.[dev]'"
    exit 1
fi

# shellcheck disable=SC1090
source "$VENV"

if ! command -v node >/dev/null 2>&1; then
  echo "[EAR Live UI] Node.js is required but was not found on PATH."
  echo "[EAR Live UI] Install Node.js LTS, restart your shell, and run this script again."
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "[EAR Live UI] npm is required but was not found on PATH."
  echo "[EAR Live UI] Install Node.js LTS, restart your shell, and run this script again."
  exit 1
fi

echo "[EAR Live UI] Starting live EAR API on http://127.0.0.1:8085 ..."
python -m ear.cli demo-server --host 127.0.0.1 --port 8085 >/dev/null 2>&1 &

cd "$(dirname "$0")/webapp"

if [ ! -d "node_modules" ]; then
  echo "[EAR Live UI] Installing web dependencies..."
  npm install
fi

echo "[EAR Live UI] Launching React app on http://127.0.0.1:5173 ..."
npm run dev
