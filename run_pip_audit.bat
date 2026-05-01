@echo off
:: ============================================================
:: run_pip_audit.bat — Run pip-audit and write JSON reports
::                     to security_reports\
:: Usage: run_pip_audit.bat
:: ============================================================
setlocal EnableDelayedExpansion

set VENV=.venv\Scripts\activate.bat
set REPORTS_DIR=security_reports

if not exist "%VENV%" (
    echo [ERROR] Virtual environment not found. Run: python -m venv .venv ^&^& .venv\Scripts\pip install -e ".[dev]"
    exit /b 1
)

call "%VENV%"

if not exist "%REPORTS_DIR%" mkdir "%REPORTS_DIR%"

:: Timestamp for uniquely named report files (YYYYMMDD_HHMMSS)
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value 2^>nul') do set DT=%%I
set TIMESTAMP=%DT:~0,8%_%DT:~8,6%

set REPORT_JSON=%REPORTS_DIR%\pip_audit_%TIMESTAMP%.json
set REPORT_CYCLONE=%REPORTS_DIR%\pip_audit_cyclonedx_%TIMESTAMP%.json
set LATEST_JSON=%REPORTS_DIR%\pip_audit_latest.json

echo.
echo ============================================================
echo  Running pip-audit — dependency vulnerability scan
echo ============================================================
echo.

:: Run audit and write both JSON and CycloneDX output.
:: pip-audit exits non-zero when vulnerabilities are found.
python -m pip_audit --format=json --output="%REPORT_JSON%" --progress-spinner=off
set AUDIT_EXIT=%ERRORLEVEL%

python -m pip_audit --format=cyclonedx-json --output="%REPORT_CYCLONE%" --progress-spinner=off 2>nul
:: CycloneDX exit code is secondary; don't abort on it.

:: Copy to a stable "latest" name for dashboards / CI artefacts.
copy /Y "%REPORT_JSON%" "%LATEST_JSON%" >nul

echo.
echo ============================================================
echo  pip-audit reports written to %REPORTS_DIR%\
echo    JSON     : %REPORT_JSON%
echo    CycloneDX: %REPORT_CYCLONE%
echo    Latest   : %LATEST_JSON%
if %AUDIT_EXIT% EQU 0 (
    echo  Status: No vulnerabilities found.
) else (
    echo  Status: VULNERABILITIES DETECTED. Review %REPORT_JSON%
)
echo ============================================================
echo.

exit /b %AUDIT_EXIT%
