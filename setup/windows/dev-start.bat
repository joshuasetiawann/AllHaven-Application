@echo off
REM AllHaven - DEVELOPER start: backend + frontend natively, each in its own window.
REM Prereqs: Python 3.11+, Node 18+, and a reachable PostgreSQL (set DATABASE_URL in backend\.env).
REM
REM Installing AllHaven to use it? Run AllHaven.bat (or AllHaven-Setup.exe) instead -
REM that runs the whole stack in Docker and needs no Python or Node.

setlocal
set ROOT=%~dp0..\..

echo Starting AllHaven backend...
cd /d "%ROOT%\backend"
REM Use the py launcher: bare `python` on Windows often hits the Store alias stub.
if not exist .venv (
  py -3 -m venv .venv || python -m venv .venv
)
start "AllHaven Backend" cmd /k ".venv\Scripts\activate && pip install -r requirements.txt && alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"

echo Starting AllHaven frontend...
cd /d "%ROOT%\frontend"
if not exist node_modules (
  call npm install
)
start "AllHaven Frontend" cmd /k "npm run dev"

echo.
echo AllHaven is starting:
echo   Backend : http://localhost:8000   (docs at /docs)
echo   Frontend: http://localhost:3000
echo Close the two opened windows (or run scripts\stop.bat) to stop.
endlocal
