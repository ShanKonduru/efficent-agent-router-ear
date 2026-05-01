#!/usr/bin/env bash
# ============================================================
# run_trivy.sh — Run Trivy filesystem vulnerability scan
#                and write reports to security_reports/
#
# Prerequisites: trivy must be on PATH.
#   Linux/macOS: https://aquasecurity.github.io/trivy/latest/getting-started/installation/
#   macOS:       brew install trivy
#
# Usage: ./run_trivy.sh [trivy-extra-args...]
# ============================================================
set -uo pipefail

REPORTS_DIR="security_reports"
SCAN_TARGET="."

if ! command -v trivy &>/dev/null; then
    echo "[ERROR] trivy not found on PATH."
    echo "        macOS  : brew install trivy"
    echo "        Linux  : https://aquasecurity.github.io/trivy/latest/getting-started/installation/"
    exit 1
fi

mkdir -p "$REPORTS_DIR"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_JSON="${REPORTS_DIR}/trivy_${TIMESTAMP}.json"
REPORT_SARIF="${REPORTS_DIR}/trivy_${TIMESTAMP}.sarif"
REPORT_TABLE="${REPORTS_DIR}/trivy_${TIMESTAMP}.txt"
LATEST_JSON="${REPORTS_DIR}/trivy_latest.json"
LATEST_SARIF="${REPORTS_DIR}/trivy_latest.sarif"

IGNORE_FLAG=""
if [[ -f ".trivyignore" ]]; then
    IGNORE_FLAG="--ignorefile .trivyignore"
fi

echo
echo "============================================================"
echo " Running Trivy filesystem scan on: ${SCAN_TARGET}"
echo "============================================================"
echo

# Table to console for quick human review
# shellcheck disable=SC2086
trivy fs \
    --exit-code 0 \
    --scanners vuln,misconfig,secret \
    --severity HIGH,CRITICAL \
    $IGNORE_FLAG \
    --format table \
    "$SCAN_TARGET" "$@"

# JSON — machine-readable archive; exit-code 1 on findings (for CI gating)
# shellcheck disable=SC2086
trivy fs \
    --exit-code 1 \
    --scanners vuln,misconfig,secret \
    --severity HIGH,CRITICAL \
    $IGNORE_FLAG \
    --format json \
    --output "$REPORT_JSON" \
    "$SCAN_TARGET"
TRIVY_EXIT=$?

# SARIF — for GitHub Advanced Security / Code Scanning upload
# shellcheck disable=SC2086
trivy fs \
    --exit-code 0 \
    --scanners vuln,misconfig,secret \
    --severity HIGH,CRITICAL \
    $IGNORE_FLAG \
    --format sarif \
    --output "$REPORT_SARIF" \
    "$SCAN_TARGET" 2>/dev/null || true

# Table saved to file
# shellcheck disable=SC2086
trivy fs \
    --exit-code 0 \
    --scanners vuln,misconfig,secret \
    --severity HIGH,CRITICAL \
    $IGNORE_FLAG \
    --format table \
    --output "$REPORT_TABLE" \
    "$SCAN_TARGET" 2>/dev/null || true

cp "$REPORT_JSON"  "$LATEST_JSON"
cp "$REPORT_SARIF" "$LATEST_SARIF"

echo
echo "============================================================"
echo " Trivy reports written to ${REPORTS_DIR}/"
echo "   JSON  : ${REPORT_JSON}"
echo "   SARIF : ${REPORT_SARIF}"
echo "   Table : ${REPORT_TABLE}"
if [[ $TRIVY_EXIT -eq 0 ]]; then
    echo " Status: No HIGH/CRITICAL findings."
else
    echo " Status: HIGH/CRITICAL findings detected. Review ${REPORT_JSON}"
fi
echo "============================================================"
echo

exit $TRIVY_EXIT
