@echo off
setlocal

echo [EAR Demo] Running demo smoke tests...
python -m pytest tests/test_demo_backend.py -q
if errorlevel 1 (
  echo [EAR Demo] Smoke tests failed. Aborting walkthrough.
  exit /b 1
)

echo [EAR Demo] Starting local demo API on http://127.0.0.1:8085 ...
start "EAR Demo API" python -m ear.cli demo-server --host 127.0.0.1 --port 8085

echo [EAR Demo] Opening leadership demo UI...
start "" "docs\llm_explorer.html"

echo [EAR Demo] Walkthrough ready.
exit /b 0
