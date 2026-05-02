#!/usr/bin/env bash
set -euo pipefail

echo "[EAR Demo] Running demo smoke tests..."
python -m pytest tests/test_demo_backend.py -q

echo "[EAR Demo] Starting local demo API on http://127.0.0.1:8085 ..."
python -m ear.cli demo-server --host 127.0.0.1 --port 8085 >/dev/null 2>&1 &

echo "[EAR Demo] Opening leadership demo UI..."
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open docs/llm_explorer.html >/dev/null 2>&1 || true
elif command -v open >/dev/null 2>&1; then
  open docs/llm_explorer.html >/dev/null 2>&1 || true
fi

echo "[EAR Demo] Walkthrough ready."
