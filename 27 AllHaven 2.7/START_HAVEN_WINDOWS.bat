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

REM Terminal installer. First run installs & starts Haven in THIS window (no
REM website). After setup it just starts services and opens the app.
REM   HAVEN_FORCE_SETUP=1  re-run the installer even when configured
REM   HAVEN_SETUP_WEB=1    use the optional browser wizard instead
if "%HAVEN_SETUP_WEB%"=="1" (
  echo Opening the optional browser setup wizard ^(HAVEN_SETUP_WEB=1^)...
  "%PY%" "%ROOT%installer\haven_setup.py"
  goto :done
)
if "%HAVEN_FORCE_SETUP%"=="1" goto :install
if not exist "%ROOT%.env" goto :install
echo Starting Haven and opening the app...
"%PY%" "%ROOT%installer\haven_launch.py"
goto :done
:install
echo Installing ^& starting Haven in this terminal...
"%PY%" "%ROOT%installer\haven_cli.py"
:done
endlocal
