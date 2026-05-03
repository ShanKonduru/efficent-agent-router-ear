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
for /f "tokens=*" %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set TIMESTAMP=%%i

set REPORT_JSON=%REPORTS_DIR%\pip_audit_%TIMESTAMP%.json
set REPORT_CYCLONE=%REPORTS_DIR%\pip_audit_cyclonedx_%TIMESTAMP%.json
set LATEST_JSON=%REPORTS_DIR%\pip_audit_latest.json
set REPORT_HTML=%REPORTS_DIR%\pip_audit_%TIMESTAMP%.html
set LATEST_HTML=%REPORTS_DIR%\pip_audit_latest.html

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

:: Check if JSON report was created before proceeding
if not exist "%REPORT_JSON%" (
    echo [ERROR] pip-audit did not produce a report. Exit code: %AUDIT_EXIT%
    echo [ERROR] Check if pip-audit is installed: python -m pip install pip-audit
    exit /b %AUDIT_EXIT%
)

:: Copy to a stable "latest" name for dashboards / CI artefacts.
copy /Y "%REPORT_JSON%" "%LATEST_JSON%" >nul

where srk >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [INFO] sec-report-kit not found. Installing into current environment...
    python -m pip install sec-report-kit >nul
)

set RENDER_EXIT=0
where srk >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    srk render pip-audit --input "%REPORT_JSON%" --output "%REPORT_HTML%" --target pyproject.toml
    set RENDER_EXIT=%ERRORLEVEL%
    if !RENDER_EXIT! EQU 0 (
        copy /Y "%REPORT_HTML%" "%LATEST_HTML%" >nul
    )
) else (
    echo [WARN] Unable to find srk after install attempt. HTML report not generated.
    set RENDER_EXIT=2
)

if %AUDIT_EXIT% EQU 0 if NOT %RENDER_EXIT% EQU 0 set AUDIT_EXIT=%RENDER_EXIT%

echo.
echo ============================================================
echo  pip-audit reports written to %REPORTS_DIR%\
echo    JSON     : %REPORT_JSON%
echo    CycloneDX: %REPORT_CYCLONE%
echo    Latest   : %LATEST_JSON%
if %RENDER_EXIT% EQU 0 (
    echo    HTML     : %REPORT_HTML%
    echo    Latest   : %LATEST_HTML%
)
if %AUDIT_EXIT% EQU 0 (
    echo  Status: No vulnerabilities found.
) else (
    echo  Status: VULNERABILITIES DETECTED. Review %REPORT_JSON%
)
echo ============================================================
echo.

exit /b %AUDIT_EXIT%
