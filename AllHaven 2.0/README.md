# AllHaven Command Center

A modular **AI command center dashboard** for personal and company productivity.

> AllHaven is **not** an operating system. It is a local-first web application (FastAPI + Next.js)
> that combines tasks, notes, finance tracking, and an AI assistant — where **the AI proposes and
> humans approve** every write action.

This repository is a complete, runnable **local MVP**.

**Version:** see [`VERSION`](VERSION) · what changed each release: [`CHANGELOG.md`](CHANGELOG.md)
· how versions work: [`docs/VERSIONING.md`](docs/VERSIONING.md) · per-release notes: [`docs/releases/`](docs/releases/)

---

## Highlights

- **FastAPI** backend with a clean layered architecture (api → schemas → services → domain → core)
- **PostgreSQL** + **SQLAlchemy 2.x** + **Alembic** migration
- Standard success/error response envelopes and centralized exception handling
- Local MVP **auth boundary** (register / login / me) — replaceable by Supabase Auth
- **Workspace-scoped** business data, **soft deletes**, and **audit logging**
- Tasks, Notes, Finance (categories, transactions, monthly summary) CRUD
- **Multi-agent AI chat**: run up to **3 agents concurrently**, each answering in its own card
- **9 AI providers**: Ollama (local) + GPT, Claude, Gemini, Grok, Blackbox, and **3 independent OpenRouter slots**
- **Human-in-the-loop AI**: honest "not configured" responses, no fake execution
- Honest **integration status** & **real verification** (online only after a successful test; no faked connections, no secret leakage)
- **Local `.env` mirror**: web Settings persist to the DB and mirror allowed keys to `.env` (allowlist + backup + atomic write)
- **MVP modules**: Drive (local files), Calendar (local events), Weather (honest fetch), Automations (disabled-safe drafts)
- **Next.js (App Router)** + **TypeScript** + **Tailwind** premium dark UI, responsive, wired to the API

---

## Project structure

```
CORE-OS-APPLICATION/
├── README.md
├── .env.example
├── docker-compose.yml          # PostgreSQL (optional services documented only)
├── docs/                       # ARCHITECTURE, MVP_SCOPE, SECURITY_MODEL, AI_TOOL_POLICY
├── backend/                    # FastAPI app, Alembic, tests
│   ├── app/
│   │   ├── api/                # routers + dependencies
│   │   ├── core/               # config, db, security, responses, exceptions
│   │   ├── domain/             # SQLAlchemy models
│   │   ├── schemas/            # Pydantic contracts
│   │   └── services/           # business logic + audit + integrations
│   ├── alembic/                # migration environment + versions
│   └── tests/                  # pytest suite (SQLite, no external services)
└── frontend/                   # Next.js App Router UI
    ├── app/                    # routes (login, dashboard/*)
    ├── components/             # ui/ + layout/
    ├── lib/                    # api client, auth, formatting
    └── types/
```

---

## Prerequisites

- **Python** 3.11+
- **Node.js** 18+ (tested on 22)
- **PostgreSQL** 14+ — via Docker Compose **or** a local install

---

## Quick start

> **Fastest:** `./scripts/start.sh` (Linux/macOS) or `scripts\start.bat` (Windows) starts
> backend + frontend. `./scripts/healthcheck.sh` verifies them. Full guide:
> [`docs/LOCAL_SETUP.md`](./docs/LOCAL_SETUP.md). Deploy: [`docs/DEPLOYMENT.md`](./docs/DEPLOYMENT.md).
> Release status: [`docs/RELEASE_CHECKLIST.md`](./docs/RELEASE_CHECKLIST.md).

### Manual

### 1) Configure environment

```bash
cp .env.example .env
# Edit .env and set a strong SECRET_KEY.
```

The backend also reads `.env` from the `backend/` directory. The simplest setup is to copy
the same file there:

```bash
cp .env backend/.env
```

### 2) Start PostgreSQL

**Option A — Docker (recommended):**

```bash
docker compose up -d postgres
```

**Option B — Local PostgreSQL:** create a database/user that matches your `.env`
(default user `allhaven`, password `allhaven`, database `allhaven`).

### 3) Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Apply the database schema
alembic upgrade head

# Run the API (http://localhost:8000, docs at /docs)
uvicorn app.main:app --reload --port 8000
```

Health check: <http://localhost:8000/api/v1/health>

### 4) Frontend

In a second terminal:

```bash
cd frontend
cp .env.local.example .env.local   # points at http://localhost:8000/api/v1
npm install
npm run dev                        # http://localhost:3000
```

Open <http://localhost:3000>, register an account, and you're in.

---

## Testing & verification

```bash
# Backend tests (uses in-memory SQLite — no external services needed)
cd backend && source .venv/bin/activate && pytest

# Frontend production build
cd frontend && npm run build
```

---

## API overview (prefix `/api/v1`)

| Area     | Endpoints |
|----------|-----------|
| Health   | `GET /health` |
| Auth     | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` |
| Tasks    | `GET/POST /tasks`, `GET/PATCH/DELETE /tasks/{id}` |
| Notes    | `GET/POST /notes`, `GET/PATCH/DELETE /notes/{id}` |
| Finance  | `GET/POST /finance/categories`, `PATCH/DELETE /finance/categories/{id}`, `GET/POST /finance/transactions`, `GET/PATCH/DELETE /finance/transactions/{id}`, `GET /finance/summary` |
| AI       | `GET/POST /ai/sessions`, `GET /ai/sessions/{id}`, `GET /ai/sessions/{id}/messages`, `POST /ai/chat`, **`POST /ai/chat/multi`**, **`GET /ai/runs/{id}`**, `GET /ai/proposals`, `POST /ai/proposals/{id}/reject` |
| AI config| `GET /ai/providers`, `PUT /ai/providers/{id}`, `POST /ai/providers/{id}/test\|enable\|disable`, `GET/PUT /ai/policy` |
| Settings | `GET /settings/integrations`, `PUT /settings/integrations/{id}`, `POST /settings/integrations/{id}/test\|enable\|disable` |
| Calendar | `GET/POST /calendar/events`, `PUT/DELETE /calendar/events/{id}` |
| Drive    | `GET/POST /drive/files`, `GET /drive/files/{id}/download`, `DELETE /drive/files/{id}` |
| Automations | `GET/POST /automations`, `PUT/DELETE /automations/{id}` |
| Weather  | `GET/POST /weather/locations`, `DELETE /weather/locations/{id}`, `GET /weather/current` |

All endpoints (except health and auth register/login) require authentication: the
browser uses an **HttpOnly session cookie** (set on login; CSRF header required on
state-changing requests; `POST /auth/refresh` rotates it, `POST /auth/logout`
revokes it server-side), while API clients/tools can use a **bearer token**.

---

## Multi-agent AI, modules & `.env` sync

- **Multi-agent chat** (`POST /ai/chat/multi`): send one message to up to **3 agents** at once
  (`provider_ids: [...]`, max 3 — more returns HTTP 422). Agents run concurrently; one agent
  failing never fails the others. Each result is persisted (`ai_multi_agent_runs` /
  `ai_agent_responses`) with an honest per-agent status: `completed`, `error`, `not_configured`,
  `disabled`, or `blocked` (external disabled by policy).
- **Three OpenRouter agents** (`openrouter_1/2/3`): each has its own API key, default model,
  status, and `OPENROUTER_{1,2,3}_API_KEY` / `_DEFAULT_MODEL` env keys.
- **Real verification**: saving a key sets status `configured` — never `online`. `online`
  requires a successful Test Connection. Random/invalid keys fail; OpenRouter is verified via its
  authenticated `/key` endpoint (its `/models` is public); Blackbox stays `configured` (no honest
  verification endpoint); Ollama is `online` only when `/api/tags` responds.
- **`.env` mirror**: the database is the runtime source of truth. In local mode, saving allowed
  keys in the web UI also mirrors them to the repo-root `.env` (timestamped `.env.bak.<ts>` backup,
  atomic write, `chmod 600`). Only an **allowlist** of keys is ever written — arbitrary keys are
  rejected. Each save response includes an `env_sync` status (`success` / `failed` / `skipped`).
  Inspect with `cat .env` and `ls -lh .env.bak.*`.
- **Modules**: Drive stores file bytes under a local storage root (metadata in `drive_files`,
  path-traversal blocked); Calendar/Automations/Weather-locations persist in PostgreSQL; Weather
  returns `setup_required` until a Weather API key is configured (never faked data). AllHaven does
  **not** execute automations — they are disabled-safe drafts.

### Ollama (local AI) setup

```bash
# Install from https://ollama.com, then:
ollama serve                 # starts the local server on :11434
ollama pull llama3.1         # pull a model (only when you choose to)
curl http://localhost:11434/api/tags   # verify; this is what Test Connection calls
```
Set `OLLAMA_BASE_URL=http://localhost:11434` (and optionally `OLLAMA_DEFAULT_MODEL`) in `.env`,
or configure it in **Settings → AI Providers**.

### Known limitations

- The `.env` mirror is process/host-global; with multiple workspaces, the last save wins for a
  given key (the DB remains per-workspace and authoritative).
- Changing process-level settings (DB URL, CORS) still needs a backend restart; live provider keys
  use the DB immediately.
- Multi-agent fan-out uses a thread pool (sync provider adapters); agents share a per-run timeout.
- Automations are never executed; n8n/Google statuses are reported honestly but no workflow runs.

---

## Trust & safety model

- The AI **never** creates, updates, or deletes data on its own. It can only propose; a human approves.
- Approval/execution of AI proposals is **intentionally not implemented** in this MVP.
- Finance is **cashflow tracking only** — never financial advice, never money movement.
- Integrations show an honest **"not configured"** state instead of faking a connection.
- Business data is always **workspace-scoped**; the client can never supply its own `workspace_id`.
- User content is **soft-deleted**; meaningful actions are written to an append-only **audit log**.

See [`docs/`](./docs) for architecture, scope, security model, and AI tool policy.

---

## Notes on the local auth implementation

For a reliable one-shot local build, password hashing (PBKDF2-HMAC-SHA256) and JWT (HS256)
are implemented with the Python standard library in `backend/app/core/security.py`. They are
isolated behind the auth boundary and documented as replaceable by bcrypt / Supabase Auth in
production (see `docs/SECURITY_MODEL.md`).
