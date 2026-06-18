# AllHaven — Local Setup

Run the whole app (backend + frontend + PostgreSQL) on your machine.

## Prerequisites
- **Python 3.11+**, **Node 18+**, and **PostgreSQL** (local install or Docker).
- Optional: **Ollama** for free local AI (https://ollama.com).

## Fastest path

### Linux / macOS
```bash
# One command: sets up + runs backend and frontend.
./scripts/start.sh          # (delegates to ./allhaven.sh run)
# Stop:
./scripts/stop.sh
# Health check (backend, frontend, database):
./scripts/healthcheck.sh
```
The start script prints both a `localhost` URL and your **LAN URL**, so phones/tablets
on the same Wi-Fi can open it too (the API auto-follows the host — no rebuild).

### Windows
```bat
scripts\start.bat
scripts\stop.bat
```

## Manual path (any OS)
```bash
# 1) Environment
cp .env.example .env        # set a strong SECRET_KEY + SETTINGS_ENCRYPTION_KEY
                            # set DATABASE_URL to your Postgres, e.g.
                            # postgresql+psycopg://allhaven:allhaven@localhost:5432/allhaven

# 2) Backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head        # create/upgrade the schema
uvicorn app.main:app --host 0.0.0.0 --port 8000      # docs at /docs

# 3) Frontend (new terminal)
cd frontend
npm install
npm run dev                 # http://localhost:3000
```

## Configuring providers & integrations
Everything is configured in the web UI (encrypted, server-side):
- **Settings → AI Providers** — Ollama / OpenAI / Claude / Gemini / Grok / Blackbox /
  OpenRouter 1-3. Paste a key, **Test Connection** → Online (only after a real check).
- **Settings → Connected Tools** — PostgreSQL, Supabase, n8n, Google, Weather, Drive.
- **Settings → Privacy & Safety** — turn ON *Allow external AI providers* to chat with
  cloud models (OFF by default for privacy).

Saved values are stored in the database and (in local mode) mirrored to the repo-root
`.env` for convenience — allowlisted keys only, with a timestamped `.env.bak.<ts>` backup.

## Notes / limitations
- **`DATABASE_URL` and `SECRET_KEY` are intentionally NOT editable from the web** (they
  bootstrap the app; changing them at runtime would break it). Edit `.env` directly and
  restart for those.
- External AI hosts must be reachable from the backend. On a restricted network (egress
  allowlist), blocked hosts are reported honestly as **"unavailable / network policy"**,
  not as a key error.
- Ollama must be running (`ollama serve`) and a model pulled for it to go Online.
