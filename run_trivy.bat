@echo off
:: ============================================================
:: run_trivy.bat — Run Trivy filesystem vulnerability scan
::                 and write reports to security_reports\
::
:: Prerequisites: trivy must be on PATH.
::   Download: https://github.com/aquasecurity/trivy/releases
::   Or: winget install AquaSecurity.Trivy
::
:: Usage: run_trivy.bat [trivy-extra-args...]
:: ============================================================
setlocal EnableDelayedExpansion

set VENV=.venv\Scripts\activate.bat
set REPORTS_DIR=security_reports

if not exist "%VENV%" (
    echo [ERROR] Virtual environment not found. Run: python -m venv .venv ^&^& .venv\Scripts\pip install -e ".[dev]"
    exit /b 1
)

call "%VENV%"
set SCAN_TARGET=.
set IGNOREFILE_ARG=
set SCANNERS=vuln,misconfig
set SKIP_ARGS=--skip-dirs .venv --skip-dirs .git --skip-dirs coverage_reports --skip-dirs security_reports

:: Check trivy is available
where trivy >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    set WINGET_TRIVY=%LOCALAPPDATA%\Microsoft\WinGet\Packages\AquaSecurity.Trivy_Microsoft.Winget.Source_8wekyb3d8bbwe
    if exist "!WINGET_TRIVY!\trivy.exe" (
        set "PATH=!WINGET_TRIVY!;%PATH%"
    ) else (
        echo [ERROR] trivy not found on PATH.
        echo         Install via: winget install AquaSecurity.Trivy
        echo         Or download from: https://github.com/aquasecurity/trivy/releases
        exit /b 1
    )
)

if not exist "%REPORTS_DIR%" mkdir "%REPORTS_DIR%"

:: Timestamp
for /f "tokens=*" %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set TIMESTAMP=%%i

set REPORT_JSON=%REPORTS_DIR%\trivy_%TIMESTAMP%.json
set LATEST_JSON=%REPORTS_DIR%\trivy_latest.json
set REPORT_HTML=%REPORTS_DIR%\trivy_%TIMESTAMP%.html
set LATEST_HTML=%REPORTS_DIR%\trivy_latest.html

if exist ".trivyignore" (
    set "IGNOREFILE_ARG=--ignorefile .trivyignore"
) else (
    echo [INFO] .trivyignore not found - scanning all files.
)

echo.
echo ============================================================
echo  Running Trivy filesystem scan on: %SCAN_TARGET%
echo ============================================================
echo.

:: JSON report (machine-readable, for archiving and CI gating)
trivy fs ^
    --exit-code 1 ^
    --scanners %SCANNERS% ^
    --severity HIGH,CRITICAL ^
    !IGNOREFILE_ARG! ^
    %SKIP_ARGS% ^
    --format json ^
    --output "%REPORT_JSON%" ^
    %SCAN_TARGET% %*
set TRIVY_EXIT=%ERRORLEVEL%

:: Check if JSON report was created before proceeding
if not exist "%REPORT_JSON%" (
    echo [ERROR] Trivy did not produce a report. Exit code: %TRIVY_EXIT%
    echo [ERROR] Ensure trivy is installed and accessible.
    exit /b %TRIVY_EXIT%
)

copy /Y "%REPORT_JSON%"  "%LATEST_JSON%"  >nul 2>&1

where srk >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    where python >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo [INFO] sec-report-kit not found. Installing with python -m pip...
        python -m pip install sec-report-kit >nul
    )
)

set RENDER_EXIT=0
where srk >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    srk render trivy --input "%REPORT_JSON%" --output "%REPORT_HTML%" --target .
    set RENDER_EXIT=%ERRORLEVEL%
    if !RENDER_EXIT! EQU 0 (
        copy /Y "%REPORT_HTML%" "%LATEST_HTML%" >nul
    )
) else (
    echo [WARN] Unable to find srk after install attempt. HTML report not generated.
    set RENDER_EXIT=2
)

if %TRIVY_EXIT% EQU 0 if NOT %RENDER_EXIT% EQU 0 set TRIVY_EXIT=%RENDER_EXIT%

echo.
echo ============================================================
echo  Trivy reports written to %REPORTS_DIR%\
echo    JSON  : %REPORT_JSON%
if %RENDER_EXIT% EQU 0 (
    echo    HTML  : %REPORT_HTML%
    echo    Latest: %LATEST_HTML%
)
if %TRIVY_EXIT% EQU 0 (
    echo  Status: No HIGH/CRITICAL findings.
) else (
    echo  Status: HIGH/CRITICAL findings detected. Review %REPORT_JSON%
)
echo ============================================================
echo.

exit /b %TRIVY_EXIT%
