@echo off
:: ============================================================
:: run_tests.bat — Run EAR unit tests with coverage report
:: Usage: run_tests.bat [pytest-args...]
:: ============================================================
setlocal EnableDelayedExpansion

set VENV=.venv\Scripts\activate.bat
set REPORTS_DIR=coverage_reports

if not exist "%VENV%" (
    echo [ERROR] Virtual environment not found. Run: python -m venv .venv ^&^& .venv\Scripts\pip install -e ".[dev]"
    exit /b 1
)

call "%VENV%"

if not exist "%REPORTS_DIR%" mkdir "%REPORTS_DIR%"

echo.
echo ============================================================
echo  Running EAR unit tests with branch coverage
echo ============================================================
echo.

python -m pytest tests/ ^
    --cov=ear ^
    --cov-branch ^
    --cov-report=term-missing ^
    --cov-report=html:%REPORTS_DIR%\html ^
    --cov-report=xml:%REPORTS_DIR%\coverage.xml ^
    --cov-report=json:%REPORTS_DIR%\coverage.json ^
    -v %*

set EXIT_CODE=%ERRORLEVEL%

echo.
echo ============================================================
if %EXIT_CODE% EQU 0 (
    echo  All tests PASSED. Coverage reports written to %REPORTS_DIR%\
) else (
    echo  Tests FAILED. Exit code: %EXIT_CODE%
)
echo ============================================================
echo.

exit /b %EXIT_CODE%
