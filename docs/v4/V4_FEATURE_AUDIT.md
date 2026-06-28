# AllHaven v4.0.0 — Feature Audit

**Version:** 4.0.0 (`VERSION`, root `package.json`, `frontend/package.json`, `frontend/components/layout/nav.ts` → `APP_VERSION = "v4.0.0"`, `backend/app/core/version.py`, `GET /api/v1/health`). Visible on the login screen, sidebar, and Settings header.

**Type:** Local-first AI command center **web app** — Next.js 14 frontend + FastAPI backend + local Postgres, with two-way Supabase sync; Capacitor Android APK. This is **not** a real operating system.

This document audits every active module, its availability per surface (Desktop / Mobile), and its backend / Tailscale-bridge dependencies.

---

## How to read the dependency columns

- **Supabase-direct** — works on mobile with **no backend reachable**. The mobile client talks only to Supabase (data via PostgREST/RLS, auth via Supabase Auth).
- **Backend-only (setup-required)** — needs the FastAPI backend reachable (e.g. via the Tailscale Desktop Bridge). When the backend/bridge is unreachable, these render the reusable `SetupRequiredState` (`frontend/components/SetupRequiredState.tsx`) — **not** a "use the desktop app" message.
- **Bridge dependency** — whether reaching the feature on mobile relies on the Tailscale Desktop Bridge (`backend/app/services/connection_resolver.py`) to resolve a desktop-local service URL.

Connectivity is probed by `frontend/lib/connection.ts` (`isBackendUnreachable()` + `pingBackend()`). No user-facing "use desktop app" text remains anywhere in the app.

---

## Module audit (all active modules)

The mobile nav (`frontend/components/layout/nav.ts`) includes **every** active module — nothing is hidden, and Weather is absent.

| Module | Desktop | Mobile | Backend dependency | Bridge dependency | Notes / limitations |
|---|---|---|---|---|---|
| **Dashboard** (`/dashboard`) | ✅ | ✅ | No (Supabase-direct) | No | Aggregates Supabase-direct modules (tasks, finance, notes, etc.). |
| **AI Chat** (`/dashboard/ai`) | ✅ | ⚠️ Setup-required | Yes (inference) | Yes for Ollama | UI loads; **inference** needs backend. Ollama chat resolves its URL via the connection resolver (Phase 5); API-key providers run server-side. Unreachable → `SetupRequiredState`. |
| **Routine** (`/dashboard/routines`) | ✅ | ✅ | No (Supabase-direct) | No | Routines incl. recurrence expansion are Supabase-direct. **AI routine generation** needs the bridge → returns a `BRIDGE_REQUIRED` setup message (formerly the only "use desktop" message). Alarms/background scheduler **not implemented**. |
| **Task** (`/dashboard/tasks`) | ✅ | ✅ | No (Supabase-direct) | No | Tasks **and** task checklist are Supabase-direct. |
| **Finance** (`/dashboard/finance`) | ✅ | ✅ | No (Supabase-direct) | No | Supabase-direct. |
| **Notes** (`/dashboard/notes`) | ✅ | ✅ | No (Supabase-direct) | No | Supabase-direct. |
| **Approval** (`/dashboard/approvals`) | ✅ | ✅ | No (Supabase-direct) | No | AI tool proposals are Supabase-direct; two-way LWW sync requires migration **0017** (see below). |
| **Calculator** (`/dashboard/calculator`) | ✅ | ✅ | No | No | Client-side only. |
| **Clock** (`/dashboard/clock`) | ✅ | ✅ | No | No | Client-side only. |
| **Drive** (`/dashboard/drive`) `MVP` | ✅ | ⚠️ Setup-required | Yes | Yes | File storage served by backend. Unreachable → `SetupRequiredState`. |
| **Automations** (`/dashboard/automations`) `MVP` | ✅ | ⚠️ Setup-required | Yes (n8n) | Yes | n8n online **only** if a safe health/base GET on the resolved endpoint responds (no workflow execution). Limitation: the n8n sub-section shows a plain error rather than the full `SetupRequiredState` when unreachable (minor polish). |
| **AI Knowledge** (`/dashboard/ai/knowledge`) `NEW` | ✅ | ⚠️ Setup-required | Yes (upload) | Yes | Knowledge **upload** needs backend. Unreachable → `SetupRequiredState`. |
| **AI Memory** (`/dashboard/ai/memory`) `NEW` | ✅ | ✅ | No (Supabase-direct) | No | Memory **suggestions** are Supabase-direct; two-way LWW sync requires migration **0017**. |
| **Settings** (`/dashboard/settings`) | ✅ | ⚠️ Setup-required | Yes | Yes | Integrations / AI-provider config, n8n, Google, system control are backend-managed (secrets stay server-side). Includes `DesktopBridgePanel`. Unreachable → `SetupRequiredState`. |
| **Auth** (register / login) | ✅ | ✅ | No (Supabase-direct) | No | Mobile register via `provision_me` RPC (migration **0016**); login via Supabase Auth bearer. Desktop uses HttpOnly cookie + CSRF. |

> Backend-only sub-capabilities that live inside other modules and likewise need the backend reachable: **AI Chat inference**, **Drive**, **AI Knowledge upload**, **Settings / Integrations / AI-provider config**, **n8n**, **Google**, **System control**, and **routine AI generation** (bridge-required).

---

## Weather — confirmed removed ✅

Weather is **removed from active scope**. Active-code grep for `weather` is **empty**; `/dashboard/weather` returns **404**.

**Deleted:**
- Backend: `routers/weather.py`, `schemas/weather.py`, `services/weather_service.py`
- Config: `WEATHER_API_KEY`, `WEATHER_PROVIDER`; `.env.example` keys; `env_file_service` allowlist entry
- Integration status: the "Weather API" card in `integration_status_service`
- Frontend: `weatherApi` (`apiRest` + `apiSupabase`); `WeatherLocation` / `WeatherCurrent` types

**Kept (dormant, documented — dropping the table would be destructive):**
- `weather_locations` table + migrations `0004` / `0012` / `0013` + ORM model + sync entry

See [`docs/v4/WEATHER_REMOVAL_REPORT.md`](./WEATHER_REMOVAL_REPORT.md).

---

## Supabase-direct vs backend-only (summary)

**Work on mobile with no backend (Supabase-direct):**
- Tasks · Task checklist · Notes · Finance · Routines (incl. recurrence expansion) · Approvals (proposals) · AI Memory (suggestions) · Auth (register via `provision_me` RPC + login)

**Need the backend reachable (e.g. via the Tailscale bridge); show `SetupRequiredState` when unreachable:**
- Drive · AI Knowledge upload · Settings / Integrations / AI-provider config · n8n · Google · System control · AI Chat inference · Routine AI generation (`BRIDGE_REQUIRED`)

---

## Tailscale Desktop Bridge & deployment profiles

`backend/app/services/connection_resolver.py` is a pure (no-I/O) resolver that maps a desktop-local service to a URL by `connection_mode`:

`local_desktop` · `tailscale_private` · `tailscale_serve` · `tailscale_funnel` · `auto`

- **Resolve first, then test.** Ollama is **online only** if `GET /api/tags` on the resolved endpoint responds; n8n is **online only** if a safe health/base GET responds (no workflow execution).
- **Funnel safety:** `funnel_enabled` defaults **false**; the resolver returns **no URL** for funnel mode unless explicitly enabled; `auto` never uses funnel.
- Bridge fields (`connection_mode`, `tailscale_url`, `serve_url`, `funnel_url`, `funnel_enabled`) live on the Ollama + n8n integration configs (provider registry / JSON config — **no migration**).
- **Ollama chat inference** (Phase 5) resolves via the same resolver: localhost fallback only for `local`/`auto`; `tailscale` mode with no URL → honest *unavailable* (no fake response).
- **API-key AI providers** (OpenAI, Claude, Gemini, Grok, Blackbox, Cursor, DeepSeek, Qwen, OpenRouter) are **independent of Tailscale** — a test asserts `ai_provider_router` never imports the resolver. Saving a key = *Configured*; *Online* needs a real Test Connection.
- **Frontend:** `IntegrationConfigModal` renders `connection_mode` as a dropdown and `funnel_enabled` as a checkbox with a red public-exposure warning; `frontend/components/settings/DesktopBridgePanel.tsx` shows the deployment mode, the needs-bridge vs no-bridge matrix, the mobile setup checklist, and the Funnel warning.

**Deployment profiles** — `DEPLOYMENT_PROFILE` config (default `private`), exposed via `/health`:

| Profile | Intent | Bridge / secrets |
|---|---|---|
| `private` | Owner / internal | Mobile via Tailscale bridge; Ollama/n8n desktop-local |
| `client_portal` | Hosted / multi-tenant | Clients **not** prompted to connect a desktop bridge; secrets server-side; workspace isolation via Supabase RLS |
| `public_demo` | Temporary public preview | Funnel optional, **OFF** by default, requires explicit confirm |

---

## Supabase migrations — **pending** (apply before relying on these in hosted Supabase)

| Migration | Adds | Effect if missing |
|---|---|---|
| `0016_provision_me` | `SECURITY DEFINER provision_me()` RPC for standalone mobile registration (creates profile + workspace + owner membership; idempotent; adopts same-email profile) | Mobile register fails: *"Could not find the function public.provision_me in the schema cache"* |
| `0017_proposal_sync_fields` | `updated_at` + `error_message` on `ai_tool_proposals`; `updated_at` on `ai_memory_suggestions`; a `set_updated_at` trigger | Proposals/suggestions are **not** two-way LWW synced; approve/reject won't converge desktop↔mobile and failed approvals don't stay visible |

**Apply via:**

```bash
cd backend && ALLHAVEN_DB_TARGET=supabase DATABASE_URL=<supabase> alembic upgrade head
```

Or paste `docs/deploy/provision_me.sql` into the Supabase SQL editor for `0016`.

> The Supabase project currently has **email confirmation ON** (`mailer_autoconfirm=false`). Disable it (Auth → Providers → Email) for instant register; otherwise the flow is register → confirm-email → login.

---

## Security posture

- Secrets stored **backend-only**, encrypted at rest (local MVP scheme); never in the frontend bundle or `localStorage`; service-role key backend-only.
- No `.env` tracked (gitignored); `.env.example` holds placeholders only.
- Funnel **off by default**; raw Ollama/n8n never exposed publicly by default.
- Auth: HttpOnly cookie + CSRF on desktop REST; Supabase Auth bearer on mobile.
- RLS workspace isolation (`app_user_id()`, `is_member()`).
- `build:mobile` self-cleans its `.next` so it cannot contaminate the web build's CSS.

---

## Verification status

- **Backend:** `pytest` — **471 passed** (deterministic, `-p no:randomly`).
  - New v4 tests: `tests/test_version.py` (version endpoint + cross-source consistency); `tests/test_desktop_bridge.py` (13: resolver by mode, funnel-off-by-default, honest Ollama/n8n unreachable gating, Ollama-chat-via-bridge, API-provider independence); `tests/test_ai_intent_finance.py` (33; finance-first intent + memory gating).
- **Frontend:** `tsc` 0 errors; web build + `build:mobile` compile (21 routes).
- **Route smoke:** all 15 active dashboard routes serve 200; `/dashboard/weather` 404; `layout.css` 200.

---

## Known limitations

- n8n automations sub-section shows a plain error (not the full `SetupRequiredState`) when n8n is unreachable — minor polish.
- On-device pixel/emulator QA not performed (static + dev-runtime checks only).
- Migrations `0016` / `0017` not yet applied to Supabase.
- Routine alarms / background scheduler not implemented (no fake execution).
