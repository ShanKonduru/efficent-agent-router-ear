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
SCANNERS="vuln,misconfig"
SKIP_ARGS=(--skip-dirs .venv --skip-dirs .git --skip-dirs coverage_reports --skip-dirs security_reports)

if ! command -v trivy &>/dev/null; then
    echo "[ERROR] trivy not found on PATH."
    echo "        macOS  : brew install trivy"
    echo "        Linux  : https://aquasecurity.github.io/trivy/latest/getting-started/installation/"
    exit 1
fi

mkdir -p "$REPORTS_DIR"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_JSON="${REPORTS_DIR}/trivy_${TIMESTAMP}.json"
LATEST_JSON="${REPORTS_DIR}/trivy_latest.json"
REPORT_HTML="${REPORTS_DIR}/trivy_${TIMESTAMP}.html"
LATEST_HTML="${REPORTS_DIR}/trivy_latest.html"

IGNORE_FLAG=""
if [[ -f ".trivyignore" ]]; then
    IGNORE_FLAG="--ignorefile .trivyignore"
fi

echo
echo "============================================================"
echo " Running Trivy filesystem scan on: ${SCAN_TARGET}"
echo "============================================================"
echo

# JSON - machine-readable archive; exit-code 1 on findings (for CI gating)
# shellcheck disable=SC2086
trivy fs \
    --exit-code 1 \
    --scanners "$SCANNERS" \
    --severity HIGH,CRITICAL \
    "${SKIP_ARGS[@]}" \
    $IGNORE_FLAG \
    --format json \
    --output "$REPORT_JSON" \
    "$SCAN_TARGET" "$@"
TRIVY_EXIT=$?

cp "$REPORT_JSON"  "$LATEST_JSON"

if ! command -v srk &>/dev/null; then
    if command -v python &>/dev/null; then
        echo "[INFO] sec-report-kit not found. Installing with python -m pip..."
        python -m pip install sec-report-kit >/dev/null
    fi
fi

RENDER_EXIT=0
if command -v srk &>/dev/null; then
    srk render trivy --input "$REPORT_JSON" --output "$REPORT_HTML" --target .
    RENDER_EXIT=$?
    if [[ $RENDER_EXIT -eq 0 ]]; then
        cp "$REPORT_HTML" "$LATEST_HTML"
    fi
else
    echo "[WARN] Unable to find srk after install attempt. HTML report not generated."
    RENDER_EXIT=2
fi

if [[ $TRIVY_EXIT -eq 0 && $RENDER_EXIT -ne 0 ]]; then
    TRIVY_EXIT=$RENDER_EXIT
fi

echo
echo "============================================================"
echo " Trivy reports written to ${REPORTS_DIR}/"
echo "   JSON  : ${REPORT_JSON}"
if [[ $RENDER_EXIT -eq 0 ]]; then
    echo "   HTML  : ${REPORT_HTML}"
    echo "   Latest: ${LATEST_HTML}"
fi
if [[ $TRIVY_EXIT -eq 0 ]]; then
    echo " Status: No HIGH/CRITICAL findings."
else
    echo " Status: HIGH/CRITICAL findings detected. Review ${REPORT_JSON}"
fi
echo "============================================================"
echo

exit $TRIVY_EXIT
