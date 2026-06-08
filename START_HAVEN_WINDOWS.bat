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

if exist "%ROOT%.env" (
  echo Haven is configured - starting services and opening the app...
  "%PY%" "%ROOT%installer\haven_launch.py"
) else (
  echo Welcome to Haven! Launching the setup wizard in your browser...
  "%PY%" "%ROOT%installer\haven_setup.py"
)
endlocal
