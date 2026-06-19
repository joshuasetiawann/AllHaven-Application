# Deploying AllHaven to production

This guide covers running AllHaven so it's reachable from anywhere, with HTTPS.
There are two common paths — pick one.

> Honesty note: the Docker images below could not be built inside the development
> sandbox (no Docker there), so build them on your server/machine. They follow
> standard, well-worn patterns; test the build once before going live.

---

## Option A — One server with Docker Compose (recommended)

Everything (PostgreSQL + backend + frontend + HTTPS reverse proxy) runs on a single
VPS. Caddy gets a free Let's Encrypt certificate automatically.

**Prerequisites**
- A Linux VPS (1 vCPU / 1–2 GB RAM is enough to start) with Docker + Docker Compose.
- A domain name with a DNS **A record** pointing at the server's public IP.
- Ports **80** and **443** open.

**Steps**
```bash
# On the server, in the project root:
cp .env.prod.example .env.prod
nano .env.prod              # set DOMAIN + strong POSTGRES_PASSWORD/SECRET_KEY/SETTINGS_ENCRYPTION_KEY

# Build & start the whole stack:
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build

# Watch logs (first boot runs DB migrations automatically):
docker compose -f docker-compose.prod.yml logs -f
```
Then open **https://yourdomain.com** — register the first user and you're in.

**What you get**
- `https://yourdomain.com` → frontend
- `https://yourdomain.com/api/*` → backend (same origin, so no CORS issues)
- Auto-HTTPS via Caddy; Postgres data + uploaded Drive files persist in named volumes.

**Generate strong secrets**
```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"   # SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(48))"   # SETTINGS_ENCRYPTION_KEY
```

**Update / restart / backup**
```bash
# Update after pulling new code:
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build

# Backup the database:
docker compose -f docker-compose.prod.yml exec db \
  pg_dump -U allhaven allhaven > backup_$(date +%F).sql
```

---

## Option B — Managed hosting (no server to maintain)

- **Frontend → Vercel:** import the `frontend/` folder; set env var
  `NEXT_PUBLIC_API_BASE_URL=https://<your-api-domain>/api/v1`. Deploy.
- **Backend → Render / Railway / Fly.io:** deploy `backend/` (uses its Dockerfile).
  Start command is already `alembic upgrade head && uvicorn app.main:app ...`.
- **Database → managed Postgres** (Neon, Supabase, Render PG, RDS). Put its URL in
  `DATABASE_URL` (format `postgresql+psycopg://user:pass@host:5432/db`).
- On the backend, set `APP_ENV=production` and `BACKEND_CORS_ORIGINS=https://<your-frontend-domain>`
  so the browser is allowed to call the API cross-origin.

---

## Required production environment variables (backend)

| Variable | Purpose |
|---|---|
| `APP_ENV=production` | Disables the local dev CORS wildcard; uses the explicit origin list |
| `DATABASE_URL` | `postgresql+psycopg://user:pass@host:5432/db` |
| `SECRET_KEY` | JWT signing — long random value |
| `SETTINGS_ENCRYPTION_KEY` | Encrypts saved provider/integration secrets at rest |
| `BACKEND_CORS_ORIGINS` | Your frontend origin(s), comma-separated (skip if same-origin via Caddy) |
| `DRIVE_STORAGE_DIR` | Where uploaded files live (mount a volume; default `/data/drive` in the image) |

AI provider keys (OpenAI/Anthropic/Gemini/Grok/Blackbox/OpenRouter) are best set
**in the web UI → Settings → AI Providers** (encrypted in the DB). You can also seed
them via env vars (see `.env.example`).

---

## Security checklist

- [ ] Strong, unique `SECRET_KEY` and `SETTINGS_ENCRYPTION_KEY` (never the dev defaults).
- [ ] `APP_ENV=production` (so CORS is restricted to your domain, not `*`).
- [ ] Strong database password; database not exposed publicly (only the backend reaches it).
- [ ] HTTPS only (Caddy handles this in Option A).
- [ ] Never commit `.env.prod` or any real keys (already gitignored).
- [ ] Back up the database regularly.
- [ ] Keep "Allow external AI providers" OFF unless you intend to send data to external AI.

---

## Notes on the AI providers in production

- **Ollama (local, free):** run Ollama on the server (or a GPU box) and set
  `OLLAMA_BASE_URL`. It only goes "Online" after a successful Test Connection.
- **OpenAI / Grok / OpenRouter / Gemini / Anthropic / Blackbox:** add a valid API key
  in Settings, Test Connection → Online, then chat. These need outbound internet from
  the backend (a normal server has this; a restricted egress allowlist would block
  specific hosts — AllHaven reports that honestly as "unavailable / network policy").
- **OpenRouter light models:** set a light/free model in the UI (e.g. `openai/gpt-4o-mini`,
  `meta-llama/llama-3.1-8b-instruct`, or a current `:free` model from openrouter.ai/models).
