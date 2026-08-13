<div align="center">

![AllHaven Command Center](docs/assets/banner.svg)

# AllHaven Command Center

**A local-first AI command center for personal productivity, workspace memory, finance tracking, routines, notes, and human-approved AI actions.**

The desktop app owns the private backend. The Android APK is the mobile companion: it can run core workspace features through Supabase, and only uses the desktop bridge for local services such as Ollama and n8n.

[![Version](https://img.shields.io/badge/version-4.3.0%20%7C%20AllHaven%204.3-18E0D6?style=flat-square)](CHANGELOG.md)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![Next.js 15](https://img.shields.io/badge/Next.js%2015-000000?style=flat-square&logo=nextdotjs&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-mobile%20data-3ECF8E?style=flat-square&logo=supabase&logoColor=white)
![Android](https://img.shields.io/badge/Android-APK-3DDC84?style=flat-square&logo=android&logoColor=white)

[Quick Start](#quick-start) | [Mobile APK](#mobile-apk) | [Features](#features) | [Docs](#documentation) | [Changelog](CHANGELOG.md)

</div>

---

## Status

**Current release:** `v4.3.0`

> **This is the `mobile` branch.** The source above is AllHaven 4.3.0. The Flutter
> APK shell in [`mobile_flutter/`](mobile_flutter/) is still at `4.2.0+45` — its
> bundled web assets (`mobile_flutter/assets/allhaven/`) are the 4.2 static export
> and have not been rebuilt for 4.3. Rebuild the mobile export and re-bundle it
> before bumping `mobile_flutter/pubspec.yaml`, so the APK version never claims a
> release its assets do not contain.

AllHaven is not an operating system. It is a complete web application with:

- a **FastAPI** backend;
- a **Next.js** frontend;
- a **PostgreSQL** local database;
- an optional **Supabase** cloud data layer for mobile;
- a **Capacitor Android APK** build;
- local/remote AI provider integrations with honest status checks.

### What changed in 4.3

- A full application audit found ten issues. All ten are fixed and retested, along with the extra defects an adversarial closure review turned up.
- Secrets are re-encrypted with versioned AES-256-GCM envelopes, and a CLI rotates them (`python -m app.cli.rotate_secrets`).
- Uploads and document parsers now enforce their limits *before* allocating memory — DOCX and PDF can no longer be used to exhaust the backend.
- Mobile credentials live in the iOS Keychain / Android Keystore instead of plain preferences, migrated automatically on upgrade.
- Script CSP dropped `unsafe-inline`; logout actually revokes bearer tokens; session refresh can't be replayed.
- Fake status signals removed: System Control no longer reports healthy containers as stopped, and no screen claims success on a failed or disabled operation.
- Deleting a task now asks first, and `127.0.0.1` works as a login origin again.
- Repository structure tidied — audit reports out of the root, `docs/v4/` dissolved, `docs/deploy/` renamed to `docs/sql/`.

Read more: [release notes](docs/releases/v4.3.0.md). **Run `alembic upgrade head`** before starting 4.3.0.

---

## Product Model

| Surface | Purpose | Data path |
| --- | --- | --- |
| **Desktop web app** | Full command center, local backend, local PostgreSQL, provider settings, system controls. | Browser -> FastAPI -> PostgreSQL/local services |
| **Android APK** | Mobile workspace for tasks, notes, finance, routines, approvals, memory, and AI chat UI. | APK -> Supabase for core data; optional bridge to desktop backend |
| **Backend Bridge** | Lets mobile reach desktop-only/local resources. | APK -> LAN/Tailscale/Serve URL -> FastAPI |
| **Ollama / n8n** | Remain desktop/local services by design. | Requires LAN or Tailscale bridge from mobile |

The mobile target is intentionally different from desktop: core workspace data should work without Tailscale, while local-only services use the bridge only when needed.

---

## Preview

<div align="center">

![AllHaven dashboard](docs/assets/screenshot-dashboard.png)

<sub>Dashboard: workspace status, finance, tasks, notes, approvals, and integration health.</sub>

![Multi-agent AI chat](docs/assets/screenshot-ai-chat.png)

<sub>AI Chat: multi-agent runs, memory context, human approvals, and honest provider status.</sub>

</div>

---

## Features

### Workspace

- Dashboard overview with monthly cashflow, pending work, and integration status.
- Tasks with checklist support, completion/reopen flow, and AI-generated drafts.
- Notes and knowledge entries with edit/save support.
- Routine planner for daily schedules and recurring plans.
- Finance tracking for categories, transactions, summaries, and reports.
- Approval center for AI-proposed write actions.

### AI

- Multi-agent chat with up to **10 agents**.
- Modes: single, parallel, debate, and reasoning.
- Providers: Ollama, OpenAI/GPT, Claude, Gemini, Grok, Blackbox, Cursor-compatible gateways, DeepSeek, Qwen, and six OpenRouter agents.
- AI Memory with controlled current facts and memory suggestions.
- AI Knowledge document upload/search for local context.
- Tool registry with human approval for risky writes.

### Mobile

- Android APK built from the same AllHaven UI through Capacitor.
- Supabase Auth/data mode for core mobile workflows.
- Backend Bridge URL can be changed inside the app; no rebuild required.
- Supports LAN, Tailscale private IP, MagicDNS, or Tailscale Serve.
- Ollama and n8n are optional bridge features, not requirements for login/core data.

### Safety

- No fake online states: integrations are online only after real test calls.
- Risky AI writes require human approval.
- API keys stay server-side and are shown masked.
- User content uses workspace scoping and soft-delete patterns.
- Local `.env` mirroring is allowlisted and writes atomically with backups.

---

## Architecture

```text
AllHaven-Application/
|-- backend/                  FastAPI, SQLAlchemy, Alembic, services, tests
|-- frontend/                 Next.js app, Capacitor Android project
|-- docs/                     living guides: setup, mobile, deployment, security
|   |-- releases/             per-version release notes (vX.Y.Z.md)
|   `-- reports/              audits, QA, and remediation records
|-- installer/                cross-platform install/start helpers (Python)
|-- setup/
|   |-- linux-macos/          start, stop, doctor, healthcheck
|   `-- windows/              setup wizard + control panel, .exe and installer builds
|-- deploy/                   Caddyfile and server deploy script
|-- docker-compose.yml            local PostgreSQL only (native backend/frontend)
|-- docker-compose.local.yml      full stack in Docker Desktop
|-- docker-compose.prod.yml       full stack + Caddy auto-HTTPS (needs a domain)
|-- docker-compose.prod.local.yml production stack on localhost, no domain
|-- install.sh / install.bat      first-time setup (Linux+macOS / Windows)
|-- allhaven.sh / AllHaven.bat    everyday launcher / control panel
`-- README.md
```

`docs/` holds the living guides at its root, plus `releases/` for per-version
release notes, `reports/` for point-in-time audits and QA records, `sql/` for
Supabase SQL editor scripts, `assets/` for screenshots, and `design/` for design
handoffs.

```text
Data layout — three supported modes, chosen during setup:
  both      local PostgreSQL is the database, mirrored to Supabase every 15s
  local     local PostgreSQL only, nothing leaves the machine
  supabase  the Supabase project IS the database; nothing to mirror
```

Runtime overview:

```text
Desktop browser -> Next.js dev/server -> FastAPI -> PostgreSQL
Android APK     -> static Next.js bundle -> Supabase
Android bridge  -> LAN/Tailscale/Serve URL -> FastAPI -> Ollama/n8n/local tools
```

---

## Quick Start

### Requirements

- Python `3.11+`
- Node.js `18+` for desktop; Node `22+` recommended for Capacitor 8 APK builds
- PostgreSQL `14+` or Docker
- Optional: Ollama, n8n, Supabase project, Android SDK/JDK 21 for APK builds

### One-command local install

```bash
git clone https://github.com/joshuasetiawann/AllHaven-Application.git
cd AllHaven-Application
./install.sh
```

Then open:

```text
http://localhost:3000
```

### Daily commands

| Task | Command |
| --- | --- |
| Start everything in background | `./allhaven.sh start` |
| Run in foreground | `./allhaven.sh run` |
| Restart everything | `./allhaven.sh restart` |
| Restart one service | `./allhaven.sh restart backend` or `./allhaven.sh restart frontend` |
| Stop app services | `./allhaven.sh stop` |
| Check status | `./allhaven.sh status` |
| Diagnose setup | `./setup/linux-macos/doctor.sh` |

Full guide: [Desktop setup](docs/DESKTOP_SETUP.md) and [Local setup](docs/LOCAL_SETUP.md).

---

## Run everything in Docker (Docker Desktop)

Whole stack in containers — Postgres, backend, frontend. No Python or Node needed
on the host. Migrations run automatically on backend start.

```bash
cp .env.example .env      # then set SECRET_KEY and SETTINGS_ENCRYPTION_KEY
docker compose -f docker-compose.local.yml up -d --build
```

Open `http://localhost:3000` (API at `http://localhost:8000/api/v1`).

| Task | Command |
| --- | --- |
| Status | `docker compose -f docker-compose.local.yml ps` |
| Logs | `docker compose -f docker-compose.local.yml logs -f backend` |
| Stop | `docker compose -f docker-compose.local.yml down` |
| Reset the database | `docker compose -f docker-compose.local.yml down -v` |
| Rebuild after code changes | `docker compose -f docker-compose.local.yml up -d --build` |

Notes:

- Port 5432 busy? Set `POSTGRES_HOST_PORT=5433` in `.env`.
- Ollama stays on the host; the backend reaches it at `host.docker.internal:11434`.
- `SYSTEM_CONTROL_ENABLED` is forced off — the Start/Stop controls in Settings
  need the host agent, which does not exist inside a container. Use the
  `docker compose` commands above instead.
- This is the local profile (HTTP, no domain). For a server with a real domain
  and auto-HTTPS use `docker-compose.prod.yml` — see [Deployment](docs/DEPLOYMENT.md).

---

## Manual Setup

Use this only when you do not want the installer.

```bash
cp .env.example .env
docker compose up -d postgres
```

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

Health check:

```bash
curl http://localhost:8000/api/v1/health
```

---

## Mobile APK

The APK is the existing AllHaven UI packaged with Capacitor. It is not a separate redesign.

### Build debug APK

```bash
cd frontend
NEXT_PUBLIC_API_BASE_URL=http://<desktop-ip>:8000/api/v1 \
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co \
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key> \
npm run build:mobile

npx cap sync android
cd android
./gradlew assembleDebug
```

Output:

```text
frontend/android/app/build/outputs/apk/debug/app-debug.apk
```

### Mobile connection rules

- Login/core data use Supabase in the mobile build.
- If the bridge is unreachable, tasks/notes/finance/routines that are Supabase-backed should still work.
- Ollama and n8n require the desktop bridge.
- If `http://100.x.y.z:8000/api/v1/health` fails in Chrome on the phone, the APK cannot reach that backend either.
- Prefer Tailscale Serve (`https://name.tailnet.ts.net`) when raw `100.x` IP access is blocked.

Full guide: [Mobile APK guide](docs/MOBILE.md) and [Tailscale setup](docs/TAILSCALE_SETUP.md).

---

## Configuration

Most local settings live in `.env`.

Important keys:

| Key | Purpose |
| --- | --- |
| `APP_ENV=local` | Enables local/private development behavior. |
| `DATABASE_URL` | PostgreSQL connection string. |
| `SECRET_KEY` | Backend auth signing secret. |
| `SUPABASE_URL` | Supabase project URL. |
| `SUPABASE_ANON_KEY` | Public anon key for Supabase clients. |
| `SUPABASE_SERVICE_ROLE_KEY` | Server-only Supabase admin/sync key. Never expose in frontend. |
| `SUPABASE_JWT_SECRET` | Lets desktop backend verify Supabase bearer tokens. |
| `OLLAMA_BASE_URL` | Local/Tailscale Ollama endpoint. |
| `N8N_BASE_URL` | Local/Tailscale n8n endpoint. |

See [.env.example](.env.example) for the full template.

---

## AI Providers

AllHaven supports:

| Provider | Notes |
| --- | --- |
| Ollama | Local/private models on your machine. |
| OpenAI / GPT | Cloud models through OpenAI-compatible APIs. |
| Claude | Anthropic models. |
| Gemini | Google models. |
| Grok | xAI models. |
| Blackbox | Coding-focused provider. |
| Cursor-compatible | OpenAI-compatible gateway slot. |
| DeepSeek | Chat/coding/reasoning models. |
| Qwen | Alibaba DashScope/OpenAI-compatible models. |
| OpenRouter 1-6 | Six independent agents with separate keys/models. |

Provider status is honest:

- `configured` means credentials/settings are saved.
- `online` means Test Connection actually succeeded.
- invalid keys stay offline.
- Ollama is online only when `/api/tags` responds.

---

## API Overview

All API routes use the `/api/v1` prefix.

| Area | Examples |
| --- | --- |
| Health | `GET /health` |
| Auth | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` |
| Tasks | `GET/POST /tasks`, `PATCH/DELETE /tasks/{id}` |
| Notes | `GET/POST /notes`, `PATCH/DELETE /notes/{id}` |
| Finance | categories, transactions, summaries, reports |
| Routine | `GET/POST /routines/events`, `PUT/DELETE /routines/events/{id}` |
| AI Chat | sessions, messages, multi-agent runs |
| AI Memory | memories, settings, suggestions |
| AI Knowledge | documents, indexing, search |
| Settings | integrations, AI providers, bridge/system controls |
| Drive | file metadata, upload, download, delete |
| Automations | local draft workflows and n8n bridge status |

Interactive API docs are enabled only in local mode.

---

## Testing

Backend:

```bash
cd backend
source .venv/bin/activate
pytest
```

Frontend:

```bash
cd frontend
npm run build
```

Mobile export:

```bash
cd frontend
npm run build:mobile
```

Security and setup checks:

```bash
./setup/linux-macos/doctor.sh
./setup/linux-macos/healthcheck.sh
```

---

## Troubleshooting

### Mobile login says "Something went wrong"

Rebuild the APK with:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_DATA_MODE=supabase` (already set by `npm run build:mobile`)

Then uninstall the old APK or clear app data before installing the new build.

### Phone cannot open backend URL

If Chrome on the phone cannot open:

```text
http://<desktop-ip>:8000/api/v1/health
```

the APK cannot open it either. Check:

- backend is running with `--host 0.0.0.0`;
- phone and desktop are on the same Wi-Fi or same tailnet;
- firewall allows port `8000`;
- Tailscale is connected on both devices;
- the selected URL includes `/api/v1` or lets AllHaven append it.

### Port 5432 is already in use

AllHaven can reuse a native/local PostgreSQL. To run its container on another host port:

```bash
POSTGRES_HOST_PORT=5433 docker compose up -d postgres
```

Then update `.env` accordingly.

### Broken Python venv

```bash
cd backend
mv .venv ".venv.broken.$(date +%s)"
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/alembic upgrade head
```

---

## Documentation

| Document | Purpose |
| --- | --- |
| [Desktop setup](docs/DESKTOP_SETUP.md) | Beginner install and launcher guide. |
| [Mobile guide](docs/MOBILE.md) | APK build, Backend Bridge, and Android notes. |
| [Tailscale setup](docs/TAILSCALE_SETUP.md) | Private bridge setup for phone to desktop. |
| [Deployment](docs/DEPLOYMENT.md) | Production hosting notes. |
| [Architecture](docs/ARCHITECTURE.md) | System architecture and module boundaries. |
| [Security model](docs/SECURITY_MODEL.md) | Auth, secrets, approvals, and trust boundaries. |
| [AI tool policy](docs/AI_TOOL_POLICY.md) | Tool registry and human approval rules. |
| [Supabase migration](docs/SUPABASE_MIGRATION.md) | Applying migrations to a hosted Supabase project. |
| [Versioning & downloads](docs/DOWNLOADS.md) | Where the version lives and how artifacts are named. |
| [Release notes 4.3](docs/releases/v4.3.0.md) | Current release details. |
| [Audits & reports](docs/reports/) | Security audits, feature audits, QA and remediation records. |

---

## Branches

| Branch | Role |
| --- | --- |
| `main` | Current primary release branch. |
| `master` | Kept aligned with `main` for compatibility. |
| `mobile` | Kept aligned with `main`; useful for APK/mobile-focused workflows. |

All three release branches should point at AllHaven 4.3 content.

---

## License

Copyright (c) 2026 Joshua Setiawan. All rights reserved.

AllHaven Command Center, including its source code, design, and documentation, is the intellectual property of Joshua Setiawan. See [LICENSE](LICENSE) for terms.

<div align="center">
<sub>Built with FastAPI, Next.js, PostgreSQL, Supabase, and Capacitor.</sub>
</div>
