@echo off
setlocal

set VENV=.venv\Scripts\activate.bat

if not exist "%VENV%" (
    echo [ERROR] Virtual environment not found. Run: python -m venv .venv ^&^& .venv\Scripts\pip install -e ".[dev]"
    exit /b 1
)

call "%VENV%"

where node >nul 2>&1
if errorlevel 1 goto install_node

where npm >nul 2>&1
if errorlevel 1 goto install_node

goto run_app

:install_node
echo [EAR Live UI] Node.js/npm not found. Attempting automatic install via winget...
where winget >nul 2>&1
if errorlevel 1 (
  echo [EAR Live UI] winget is not available on this machine.
  echo [EAR Live UI] Install Node.js LTS manually and rerun this script.
  exit /b 1
)

winget install OpenJS.NodeJS.LTS --silent --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
  echo [EAR Live UI] Automatic Node.js install failed.
  echo [EAR Live UI] Try running manually:
  echo   winget install OpenJS.NodeJS.LTS
  exit /b 1
)

if exist "%LocalAppData%\Programs\nodejs" (
  set "PATH=%LocalAppData%\Programs\nodejs;%PATH%"
)
if exist "%ProgramFiles%\nodejs" (
  set "PATH=%ProgramFiles%\nodejs;%PATH%"
)

where node >nul 2>&1
if errorlevel 1 (
  echo [EAR Live UI] Node.js was installed but is not visible in PATH yet.
  echo [EAR Live UI] Close and reopen terminal, then rerun this script.
  exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
  if exist "%LocalAppData%\Programs\nodejs\npm.cmd" (
    set "PATH=%LocalAppData%\Programs\nodejs;%PATH%"
  )
  if exist "%ProgramFiles%\nodejs\npm.cmd" (
    set "PATH=%ProgramFiles%\nodejs;%PATH%"
  )

  where npm >nul 2>&1
  if not errorlevel 1 goto npm_ok

  echo [EAR Live UI] npm was not found after install.
  echo [EAR Live UI] Close and reopen terminal, then rerun this script.
  exit /b 1
)

:npm_ok

echo [EAR Live UI] Node.js installation complete.

:run_app

echo [EAR Live UI] Checking for existing processes on ports 8085 and 5173...
powershell -NoProfile -Command "$ports = @(8085, 5173); foreach($p in $ports) { $conn = Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue; if($conn) { Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue } }" >nul 2>&1
timeout /t 2 /nobreak >nul

echo [EAR Live UI] Starting live EAR API on http://127.0.0.1:8085 ...
start "EAR Live API" cmd /c "python -m ear.cli demo-server --host 127.0.0.1 --port 8085 || (echo. && echo [ERROR] Backend failed to start. Press any key to close... && pause>nul)"

cd /d "%~dp0webapp"

if not exist "node_modules" (
  echo [EAR Live UI] Installing web dependencies...
  npm install
  if errorlevel 1 (
    echo [EAR Live UI] npm install failed.
    exit /b 1
  )
)

echo [EAR Live UI] Starting React app on http://127.0.0.1:5173 ...
start "EAR Live Webapp" cmd /c "cd /d %CD% && npm run dev || (echo. && echo [ERROR] React app failed to start. Press any key to close... && pause>nul)"

echo [EAR Live UI] Waiting for Vite to become ready...
set "EAR_WAIT_COUNT=0"

:wait_for_vite
powershell -NoProfile -Command "try { $r = Invoke-WebRequest 'http://127.0.0.1:5173/' -UseBasicParsing -TimeoutSec 2; exit 0 } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 goto open_browser

set /a EAR_WAIT_COUNT+=1
if %EAR_WAIT_COUNT% GEQ 30 (
  echo [EAR Live UI] Vite did not become ready in time.
  echo [EAR Live UI] Check the 'EAR Live Webapp' window for build errors.
  exit /b 1
)

timeout /t 1 /nobreak >nul
goto wait_for_vite

:open_browser
echo [EAR Live UI] Opening React app in your browser...
start "" "http://127.0.0.1:5173"
echo [EAR Live UI] Ready.
exit /b 0
