# CoreOS Command Center

A modular **AI command center dashboard** for personal and company productivity.

> CoreOS is **not** an operating system. It is a local-first web application (FastAPI + Next.js)
> that combines tasks, notes, finance tracking, and an AI assistant — where **the AI proposes and
> humans approve** every write action.

This repository is a complete, runnable **local MVP**.

---

## Highlights

- **FastAPI** backend with a clean layered architecture (api → schemas → services → domain → core)
- **PostgreSQL** + **SQLAlchemy 2.x** + **Alembic** migration
- Standard success/error response envelopes and centralized exception handling
- Local MVP **auth boundary** (register / login / me) — replaceable by Supabase Auth
- **Workspace-scoped** business data, **soft deletes**, and **audit logging**
- Tasks, Notes, Finance (categories, transactions, monthly summary) CRUD
- **Human-in-the-loop AI**: honest "not configured" responses, no fake execution
- Honest **integration status** (no faked connections, no secret leakage)
- **Next.js (App Router)** + **TypeScript** + **Tailwind** premium dark UI, wired to the API

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
(default user `coreos`, password `coreos`, database `coreos`).

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
| AI       | `GET/POST /ai/sessions`, `GET /ai/sessions/{id}`, `GET /ai/sessions/{id}/messages`, `POST /ai/chat`, `GET /ai/proposals`, `POST /ai/proposals/{id}/reject` |
| Settings | `GET /settings/integrations` |

All endpoints (except health and auth register/login) require a bearer token.

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
