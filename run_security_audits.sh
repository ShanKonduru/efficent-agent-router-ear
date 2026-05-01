#!/usr/bin/env bash
# ============================================================
# run_security_audits.sh — Run pip-audit and Trivy, including
#                          sec-report-kit HTML report rendering.
# Usage: ./run_security_audits.sh
# ============================================================
set -uo pipefail

FINAL_EXIT=0

./run_pip_audit.sh || FINAL_EXIT=$?
./run_trivy.sh || FINAL_EXIT=$?

echo
echo "============================================================"
echo " Combined security audit complete."
echo " Reports are available in security_reports/"
echo "============================================================"
echo

exit $FINAL_EXIT
