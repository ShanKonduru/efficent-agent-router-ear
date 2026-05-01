#!/usr/bin/env bash
# ============================================================
# run_pip_audit.sh — Run pip-audit and write JSON reports
#                    to security_reports/
# Usage: ./run_pip_audit.sh
# ============================================================
set -uo pipefail

VENV=".venv/bin/activate"
REPORTS_DIR="security_reports"

if [[ ! -f "$VENV" ]]; then
    echo "[ERROR] Virtual environment not found."
    echo "        Run: python -m venv .venv && .venv/bin/pip install -e '.[dev]'"
    exit 1
fi

# shellcheck disable=SC1090
source "$VENV"

mkdir -p "$REPORTS_DIR"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_JSON="${REPORTS_DIR}/pip_audit_${TIMESTAMP}.json"
REPORT_CYCLONE="${REPORTS_DIR}/pip_audit_cyclonedx_${TIMESTAMP}.json"
LATEST_JSON="${REPORTS_DIR}/pip_audit_latest.json"

echo
echo "============================================================"
echo " Running pip-audit — dependency vulnerability scan"
echo "============================================================"
echo

# pip-audit exits non-zero when vulnerabilities are found.
python -m pip_audit --format=json --output="$REPORT_JSON" --progress-spinner=off
AUDIT_EXIT=$?

python -m pip_audit --format=cyclonedx-json --output="$REPORT_CYCLONE" --progress-spinner=off 2>/dev/null || true

cp "$REPORT_JSON" "$LATEST_JSON"

echo
echo "============================================================"
echo " pip-audit reports written to ${REPORTS_DIR}/"
echo "   JSON     : ${REPORT_JSON}"
echo "   CycloneDX: ${REPORT_CYCLONE}"
echo "   Latest   : ${LATEST_JSON}"
if [[ $AUDIT_EXIT -eq 0 ]]; then
    echo " Status: No vulnerabilities found."
else
    echo " Status: VULNERABILITIES DETECTED. Review ${REPORT_JSON}"
fi
echo "============================================================"
echo

exit $AUDIT_EXIT
