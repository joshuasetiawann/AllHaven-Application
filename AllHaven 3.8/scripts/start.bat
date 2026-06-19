@echo off
REM AllHaven - start backend + frontend on Windows (each in its own window).
REM Prereqs: Python 3.11+, Node 18+, and a reachable PostgreSQL (set DATABASE_URL in backend\.env).

setlocal
set ROOT=%~dp0..

echo Starting AllHaven backend...
cd /d "%ROOT%\backend"
if not exist .venv (
  python -m venv .venv
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
