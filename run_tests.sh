#!/usr/bin/env bash
# ============================================================
# run_tests.sh — Run EAR unit tests with coverage report
# Usage: ./run_tests.sh [pytest-args...]
# ============================================================
set -euo pipefail

VENV=".venv/bin/activate"
REPORTS_DIR="coverage_reports"

if [[ ! -f "$VENV" ]]; then
    echo "[ERROR] Virtual environment not found."
    echo "        Run: python -m venv .venv && .venv/bin/pip install -e '.[dev]'"
    exit 1
fi

# shellcheck disable=SC1090
source "$VENV"

mkdir -p "$REPORTS_DIR"

echo
echo "============================================================"
echo " Running EAR unit tests with branch coverage"
echo "============================================================"
echo

python -m pytest tests/ \
    --cov=ear \
    --cov-branch \
    --cov-report=term-missing \
    --cov-report="html:${REPORTS_DIR}/html" \
    --cov-report="xml:${REPORTS_DIR}/coverage.xml" \
    --cov-report="json:${REPORTS_DIR}/coverage.json" \
    -v "$@"

EXIT_CODE=$?

echo
echo "============================================================"
if [[ $EXIT_CODE -eq 0 ]]; then
    echo " All tests PASSED. Coverage reports written to ${REPORTS_DIR}/"
else
    echo " Tests FAILED. Exit code: ${EXIT_CODE}"
fi
echo "============================================================"
echo

exit $EXIT_CODE
