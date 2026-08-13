@echo off
REM ===========================================================================
REM AllHaven - control panel for Windows.
REM
REM Start, stop, restart, check status and auto-sync, read logs, switch the
REM primary database, or re-run setup. Runs the setup wizard automatically the
REM first time, when .env.prod does not exist yet.
REM ===========================================================================
setlocal
set "HERE=%~dp0"

where py >nul 2>&1 && (set "PY=py -3") || (set "PY=python")
%PY% --version >nul 2>&1
if errorlevel 1 (
  echo.
  echo   Python 3 was not found.
  echo   Install it from https://www.python.org/downloads/ ^(tick "Add python.exe to PATH"^),
  echo   then run this file again. Or use AllHaven-Setup.exe, which needs no Python.
  echo.
  pause
  exit /b 1
)

%PY% "%HERE%allhaven_windows.py" %*
endlocal
