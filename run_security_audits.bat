@echo off
:: ============================================================
:: run_security_audits.bat — Run pip-audit and Trivy, including
::                           sec-report-kit HTML report rendering.
:: Usage: run_security_audits.bat
:: ============================================================
setlocal

set FINAL_EXIT=0

call run_pip_audit.bat
if %ERRORLEVEL% NEQ 0 set FINAL_EXIT=%ERRORLEVEL%

call run_trivy.bat
if %ERRORLEVEL% NEQ 0 set FINAL_EXIT=%ERRORLEVEL%

echo.
echo ============================================================
echo  Combined security audit complete.
echo  Reports are available in security_reports\
echo ============================================================
echo.

exit /b %FINAL_EXIT%
