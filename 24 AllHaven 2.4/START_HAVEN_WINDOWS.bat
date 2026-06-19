@echo off
REM ============================================================================
REM  Haven - one-click launcher for Windows.
REM
REM    First time:  double-click this file. It opens the setup wizard in your
REM                 browser and guides you through Docker + ports.
REM    After setup: the same double-click starts Haven and opens the app.
REM
REM  Only Python 3 is required to run the wizard.
REM ============================================================================
setlocal
set "ROOT=%~dp0"
cd /d "%ROOT%"

set "PY="
where python >nul 2>&1 && set "PY=python"
if not defined PY ( where py >nul 2>&1 && set "PY=py" )
if not defined PY (
  echo ------------------------------------------------------------
  echo  Python 3 is required to run Haven setup.
  echo  Install it from https://www.python.org/downloads/
  echo  IMPORTANT: tick "Add Python to PATH" during install.
  echo  Then double-click this file again.
  echo ------------------------------------------------------------
  pause
  exit /b 1
)

REM Default: terminal installer (live Docker/pip/npm progress, then starts the app).
REM Idempotent. Set HAVEN_SETUP_WEB=1 to use the browser-based wizard instead.
if "%HAVEN_SETUP_WEB%"=="1" (
  echo Launching the browser setup wizard ^(HAVEN_SETUP_WEB=1^)...
  "%PY%" "%ROOT%installer\haven_setup.py"
) else (
  echo Starting Haven in this terminal ^(first run installs everything automatically^)...
  "%PY%" "%ROOT%installer\haven_cli.py"
)
endlocal
