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

REM Bootstrapper only. First run (no .env) opens the browser Setup Wizard, where
REM ALL configuration happens. After setup, it starts services and opens the app.
REM   HAVEN_FORCE_WIZARD=1  re-open the wizard even when configured
REM   HAVEN_SETUP_CLI=1     use the terminal installer instead of the browser
if "%HAVEN_SETUP_CLI%"=="1" (
  echo Running the terminal installer ^(HAVEN_SETUP_CLI=1^)...
  "%PY%" "%ROOT%installer\haven_cli.py"
  goto :done
)
if "%HAVEN_FORCE_WIZARD%"=="1" goto :wizard
if not exist "%ROOT%.env" goto :wizard
echo Starting Haven and opening the app...
"%PY%" "%ROOT%installer\haven_launch.py"
goto :done
:wizard
echo Opening the Haven Setup Wizard in your browser...
"%PY%" "%ROOT%installer\haven_setup.py"
:done
endlocal
