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

set REPORTS_DIR=security_reports
set SCAN_TARGET=.

:: Check trivy is available
where trivy >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] trivy not found on PATH.
    echo         Install via: winget install AquaSecurity.Trivy
    echo         Or download from: https://github.com/aquasecurity/trivy/releases
    exit /b 1
)

if not exist "%REPORTS_DIR%" mkdir "%REPORTS_DIR%"

:: Timestamp
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value 2^>nul') do set DT=%%I
set TIMESTAMP=%DT:~0,8%_%DT:~8,6%

set REPORT_JSON=%REPORTS_DIR%\trivy_%TIMESTAMP%.json
set REPORT_SARIF=%REPORTS_DIR%\trivy_%TIMESTAMP%.sarif
set REPORT_TABLE=%REPORTS_DIR%\trivy_%TIMESTAMP%.txt
set LATEST_JSON=%REPORTS_DIR%\trivy_latest.json
set LATEST_SARIF=%REPORTS_DIR%\trivy_latest.sarif

echo.
echo ============================================================
echo  Running Trivy filesystem scan on: %SCAN_TARGET%
echo ============================================================
echo.

:: Table format to console for readability
trivy fs ^
    --exit-code 0 ^
    --scanners vuln,misconfig,secret ^
    --severity HIGH,CRITICAL ^
    --ignorefile .trivyignore 2>nul || echo (no .trivyignore found — scanning all) ^
    --format table ^
    %SCAN_TARGET% %*

:: JSON report (machine-readable, for archiving)
trivy fs ^
    --exit-code 1 ^
    --scanners vuln,misconfig,secret ^
    --severity HIGH,CRITICAL ^
    --format json ^
    --output "%REPORT_JSON%" ^
    %SCAN_TARGET%
set TRIVY_EXIT=%ERRORLEVEL%

:: SARIF report (for GitHub Code Scanning / Security tab upload)
trivy fs ^
    --exit-code 0 ^
    --scanners vuln,misconfig,secret ^
    --severity HIGH,CRITICAL ^
    --format sarif ^
    --output "%REPORT_SARIF%" ^
    %SCAN_TARGET% 2>nul

:: Table report saved to file as well
trivy fs ^
    --exit-code 0 ^
    --scanners vuln,misconfig,secret ^
    --severity HIGH,CRITICAL ^
    --format table ^
    --output "%REPORT_TABLE%" ^
    %SCAN_TARGET% 2>nul

copy /Y "%REPORT_JSON%"  "%LATEST_JSON%"  >nul 2>&1
copy /Y "%REPORT_SARIF%" "%LATEST_SARIF%" >nul 2>&1

echo.
echo ============================================================
echo  Trivy reports written to %REPORTS_DIR%\
echo    JSON  : %REPORT_JSON%
echo    SARIF : %REPORT_SARIF%
echo    Table : %REPORT_TABLE%
if %TRIVY_EXIT% EQU 0 (
    echo  Status: No HIGH/CRITICAL findings.
) else (
    echo  Status: HIGH/CRITICAL findings detected. Review %REPORT_JSON%
)
echo ============================================================
echo.

exit /b %TRIVY_EXIT%
