<div align="center">

![AllHaven Command Center](docs/assets/banner.svg)

# AllHaven Command Center

**A local-first AI command center — tasks, notes, finance, routines, workspace memory, and AI actions that wait for your approval.**

[![Version](https://img.shields.io/badge/version-4.3.0-18E0D6?style=flat-square)](CHANGELOG.md)
[![License](https://img.shields.io/badge/license-proprietary-1f2937?style=flat-square)](LICENSE)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![Next.js 15](https://img.shields.io/badge/Next.js%2015-000000?style=flat-square&logo=nextdotjs&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=flat-square&logo=supabase&logoColor=white)
![Android](https://img.shields.io/badge/Android%20APK-3DDC84?style=flat-square&logo=android&logoColor=white)

[Install](#which-one-do-i-install) · [Quick Start](#quick-start) · [Features](#features) · [Architecture](#architecture) · [Docs](#documentation) · [Changelog](CHANGELOG.md)

![AllHaven Command Center](docs/assets/screenshot-landing.png)

</div>

---

## Which one do I install?

AllHaven ships as **two different things** built from this one repository. Pick the row you want — installing the wrong one is the most common mistake.

| I want… | Install | How |
| --- | --- | --- |
| **The full app on my computer** | Desktop web app | Clone this repo and run `install.sh` / `install.bat` — see [Quick Start](#quick-start) |
| **A companion app on my Android phone** | `app-debug.apk` | Download it from [Releases](../../releases/tag/mobile-latest) |

> [!IMPORTANT]
> The APK on the Releases page is **only** the phone companion. It is not the desktop app and cannot replace it. The desktop app is not distributed as a download — you install it from source with one command.

**The phone works on its own** for tasks, notes, finance, calendar, routines, approvals, memory, and AI Knowledge — those read the workspace database directly. It needs the desktop only for Ollama, n8n, multi-agent debate, and the reasoning council. Point it at your backend in **Settings → Backend Bridge**, or add your own provider keys under **Settings → On-device AI keys** to use AI chat with no backend at all.

---

## Product Model

| Surface | Purpose | Data path |
| --- | --- | --- |
| **Desktop web app** | Full command center, local backend, local PostgreSQL, provider settings, system controls. | Browser → FastAPI → PostgreSQL / local services |
| **Android APK** | Mobile workspace: tasks, notes, finance, routines, approvals, memory, AI Knowledge, AI chat. | APK → Supabase for workspace data; optional bridge to the desktop backend |
| **Backend Bridge** | Lets the phone reach desktop-only services. | APK → LAN / Tailscale / Serve URL → FastAPI |
| **Ollama / n8n** | Desktop-local by design. | Reachable from the phone only through the bridge |

The mobile target is deliberately different from desktop: workspace data should work without a tunnel, and only genuinely local services go through the bridge.

---

## Architecture

```mermaid
flowchart LR
    subgraph Desktop["🖥️  Desktop (your machine)"]
        UI["Next.js web app"] --> API["FastAPI backend"]
        API --> PG[("PostgreSQL")]
        API --> OLL["Ollama"]
        API --> N8N["n8n"]
    end

    subgraph Cloud["☁️  Supabase"]
        SB[("Workspace database<br/>tasks · notes · finance · chat<br/>memory · knowledge · approvals")]
    end

    subgraph Phone["📱  Android APK"]
        APP["Capacitor WebView"]
    end

    API <-->|"two-way sync"| SB
    APP -->|"workspace data,<br/>works with the desktop off"| SB
    APP -.->|"Backend Bridge —<br/>only for local services"| API
    APP -.->|"on-device keys,<br/>when there is no backend"| EXT["External AI providers"]
    API --> EXT

    classDef store fill:#0b3d3a,stroke:#18E0D6,color:#d7fffb
    class PG,SB store
```

Full detail in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Preview

<div align="center">

![AllHaven dashboard](docs/assets/screenshot-dashboard.png)

<sub><b>Dashboard</b> — workspace status, finance, tasks, notes, approvals, and integration health.</sub>

<br/><br/>

![Multi-agent AI chat](docs/assets/screenshot-ai-chat.png)

<sub><b>AI Chat</b> — multi-agent runs, memory context, human approvals, and honest provider status.</sub>

<br/><br/>

![Sign in](docs/assets/screenshot-login.png)

<sub><b>Sign in</b> — one account across desktop and phone, with the backend address configurable at runtime.</sub>

</div>

---


## Status

**Current release:** `v4.3.0`

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

## Repository layout

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

### What works without the desktop

The phone reads the workspace database directly, so most of the app does not need a backend at all:

| Works with the desktop off | Needs the desktop |
| --- | --- |
| Sign-in, tasks, notes, finance, calendar, routines, automations | Ollama and other local models |
| Chat history, AI Knowledge, workspace memory | n8n |
| The approval queue — proposals are created *and* executed on-device | Multi-agent debate and the reasoning council |
| AI chat, using your own keys under **Settings → On-device AI keys** | Drive file contents (only the file list syncs) |

Point the app at a backend in **Settings → Backend Bridge** when you want the desktop-only features.

**If the bridge will not connect:** open `http://<backend-host>:<port>/api/v1/health` in Chrome on the phone first. If that fails there, the APK cannot reach it either — it is a network problem, not an app problem. Prefer a Tailscale Serve URL (`https://name.tailnet.ts.net`) when raw `100.x` addresses are blocked.

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

This repository has **one branch: `main`.** Desktop and mobile are two build targets of the same source, not two branches.

Two earlier branches were retired once their work merged. Nothing was lost — both are preserved as tags:

| Tag | What it holds |
| --- | --- |
| `archive/flutter-shell-4.3.0` | The previous Flutter WebView shell, superseded by the Capacitor build |
| `archive/legacy-version-snapshots` | Per-version source snapshots from AllHaven 1.4 through 4.3 |

```bash
git fetch origin --tags
git branch mobile archive/flutter-shell-4.3.0   # restore one if ever needed
```
---

## License

Copyright (c) 2026 Joshua Setiawan. All rights reserved.

AllHaven Command Center, including its source code, design, and documentation, is the intellectual property of Joshua Setiawan. See [LICENSE](LICENSE) for terms.

<div align="center">
<sub>Built with FastAPI, Next.js, PostgreSQL, Supabase, and Capacitor.</sub>
</div>
