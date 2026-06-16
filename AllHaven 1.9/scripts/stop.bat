@echo off
REM AllHaven - stop the dev servers started by start.bat (by window title).
taskkill /FI "WINDOWTITLE eq AllHaven Backend*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq AllHaven Frontend*" /T /F >nul 2>&1
echo Stopped AllHaven dev servers (if they were running).
