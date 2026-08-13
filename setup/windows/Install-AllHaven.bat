@echo off
REM ===========================================================================
REM AllHaven - first-time setup for Windows (no .exe needed).
REM
REM Runs the setup wizard: checks Docker Desktop, installs what is missing with
REM your permission, asks which database is primary, writes .env.prod, then
REM builds and starts everything.
REM
REM Needs Python 3 on PATH. If you have AllHaven-Setup.exe, run that instead -
REM it bundles Python and needs nothing preinstalled.
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

%PY% "%HERE%allhaven_windows.py" --setup %*
endlocal
