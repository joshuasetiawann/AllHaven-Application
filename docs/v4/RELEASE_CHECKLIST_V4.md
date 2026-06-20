# AllHaven v4.0.0 — Release Checklist

> Pre-launch checklist for **AllHaven v4.0.0**, a local-first AI command center **web app** (Next.js 14 + FastAPI + local Postgres, two-way Supabase sync, Capacitor Android APK).
>
> Repo: `joshuasetiawann/AllHaven-Application` · branch `main` · target commit `786b94e`.

This document is split into:

1. **Common steps** — run for every launch.
2. **Profile A — owner / private** (`DEPLOYMENT_PROFILE=private`).
3. **Profile B — client_portal (hosted)** (`DEPLOYMENT_PROFILE=client_portal`).

> **Secrets:** never paste real secrets, service-role keys, or `DATABASE_URL` values into this doc, commits, or chat. `.env` is gitignored; only `.env.example` placeholders are tracked.

---

## 0. What's in v4.0.0 (context for sign-off)

| Area | State |
|---|---|
| Version | `4.0.0` (VERSION, root + frontend `package.json`, `frontend/components/layout/nav.ts` `APP_VERSION="v4.0.0"`, backend `app/core/version.py`) |
| Weather | **Removed** from active scope (active-code grep empty, `/dashboard/weather` → 404). `weather_locations` table + migrations 0004/0012/0013 kept dormant (dropping is destructive). |
| Mobile parity | Mobile nav includes all active modules, no Weather, no "use desktop app" text. |
| Tailscale Desktop Bridge | `connection_resolver.py` resolves Ollama/n8n by `connection_mode`; Funnel off by default. |
| Deployment profiles | `private` (default) / `client_portal` / `public_demo`, exposed via `/health`. |
| Pending Supabase migrations | **0016_provision_me**, **0017_proposal_sync_fields** (not yet applied). |

---

## 1. Common pre-launch steps (all profiles)

### 1.1 Pull latest

- [ ] `git checkout main`
- [ ] `git pull --ff-only`
- [ ] Confirm `HEAD` is at expected commit: `git rev-parse --short HEAD` → `786b94e` (or later)
- [ ] Confirm clean tree: `git status` → clean

### 1.2 Backend tests

```bash
cd backend
pytest -p no:randomly
```

- [ ] **471 passed** (deterministic; `-p no:randomly` keeps ordering stable)
- [ ] v4 suites present and green:
  - [ ] `tests/test_version.py` (version endpoint + cross-source consistency)
  - [ ] `tests/test_desktop_bridge.py` (13 — resolver by mode, funnel-off-by-default, honest Ollama/n8n unreachable gating, Ollama-chat-via-bridge, API-provider independence)
  - [ ] `tests/test_ai_intent_finance.py` (33 — finance-first intent + memory gating)

### 1.3 Frontend build + type check

```bash
cd frontend
npx tsc --noEmit
npm run build          # web build — 21 routes
npm run build:mobile   # Capacitor/Supabase-bearer build (self-cleans its own .next)
```

- [ ] `tsc` → **0 errors**
- [ ] `npm run build` compiles (21 routes)
- [ ] `npm run build:mobile` compiles
- [ ] Route smoke (dev runtime): all **15 active dashboard routes serve 200**, `/dashboard/weather` → **404**, `layout.css` → **200**

> `build:mobile` self-cleans its `.next` so it cannot contaminate the web build's CSS. Run `npm run build` again if you need a clean web artifact after a mobile build.

### 1.4 Apply Supabase migrations 0016 / 0017

> **Required before relying on standalone mobile register or two-way proposal/suggestion sync in hosted Supabase.** These are **not yet applied**.

| Migration | Adds | Why it matters |
|---|---|---|
| `0016_provision_me` | `SECURITY DEFINER public.provision_me()` RPC (creates profile + workspace + owner membership; idempotent; adopts same-email profile) | Without it, mobile register fails: `Could not find the function public.provision_me in the schema cache` |
| `0017_proposal_sync_fields` | `updated_at` + `error_message` on `ai_tool_proposals`; `updated_at` on `ai_memory_suggestions`; `set_updated_at` trigger | Makes proposals/suggestions two-way LWW synced (approve/reject converges desktop ↔ mobile; failed approvals stay visible) |

Apply via Alembic (preferred):

```bash
cd backend
ALLHAVEN_DB_TARGET=supabase DATABASE_URL=<supabase> alembic upgrade head
```

— **or** paste `docs/deploy/provision_me.sql` into the Supabase SQL editor (covers **0016** only).

- [ ] `0016_provision_me` applied
- [ ] `0017_proposal_sync_fields` applied
- [ ] Verified RPC exists (`provision_me` resolvable; register no longer errors with schema-cache message)

### 1.5 Email confirmation (Supabase Auth)

> Supabase project currently has email confirmation **ON** (`mailer_autoconfirm=false`).

Choose one:

- [ ] **Disable** for instant register: Supabase → **Auth → Providers → Email** → turn off email confirmation, **or**
- [ ] **Keep confirm flow** and accept the order: register → confirm-email → login (document this for users)

### 1.6 Set `DEPLOYMENT_PROFILE`

- [ ] Set `DEPLOYMENT_PROFILE` in backend env (config default is `private`; `backend/app/core/config.py:45`)
  - `private` — owner / internal
  - `client_portal` — hosted / multi-tenant
  - `public_demo` — temporary public preview (Funnel optional, OFF by default, explicit confirm)
- [ ] Confirm it surfaces on `GET /api/v1/health` → `deployment_profile` (`backend/app/api/routers/health.py`)

### 1.7 Build / download the Android APK

> APK is built by the existing GitHub Actions workflow `.github/workflows/android-apk.yml` (Capacitor).

- [ ] Trigger / confirm the `android-apk.yml` run on `main`
- [ ] Download the APK from the **mobile-latest** release
- [ ] Artifact filename includes **`v4.0.0`**

### 1.8 Verify version surfaces

- [ ] `GET /api/v1/health` returns `app_version` + `deployment_profile` + `env`
- [ ] **Login screen** shows `v4.0.0`
- [ ] **Sidebar** shows `v4.0.0`
- [ ] **Settings header** shows `v4.0.0`
- [ ] Cross-source consistency holds (VERSION ↔ root/frontend `package.json` ↔ `nav.ts` `APP_VERSION` ↔ backend `version.py`) — covered by `tests/test_version.py`

### 1.9 Security scan

- [ ] No `.env` tracked: `git ls-files | grep -E '(^|/)\.env$'` → empty; only `.env.example` placeholders present
- [ ] Service-role key is **backend-only**; not in frontend bundle or `localStorage`
- [ ] Secrets stored backend-only, encrypted at rest (local MVP scheme)
- [ ] Auth: desktop REST = HttpOnly cookie + CSRF; mobile = Supabase Auth bearer
- [ ] RLS workspace isolation in effect (`app_user_id()`, `is_member()`)
- [ ] **Funnel OFF by default**; raw Ollama / n8n never exposed publicly by default

### 1.10 Confirm Weather is absent

- [ ] Active-code grep for weather is **empty**
- [ ] `/dashboard/weather` → **404**
- [ ] No "Weather API" card in Integrations; no `weatherApi` / Weather types in frontend
- [ ] (Expected) `weather_locations` table + migrations 0004/0012/0013 + ORM model remain dormant — **do not drop** (destructive)
- [ ] Reference: `docs/v4/WEATHER_REMOVAL_REPORT.md`

### 1.11 Confirm Funnel is disabled

- [ ] `funnel_enabled` defaults **false**
- [ ] Resolver returns **no URL** for `funnel` mode unless explicitly enabled; `auto` **never** uses funnel
- [ ] `IntegrationConfigModal` shows the red public-exposure warning on the funnel checkbox
- [ ] `components/settings/DesktopBridgePanel.tsx` Funnel warning visible

---

## 2. Profile A — Owner / Private launch (`DEPLOYMENT_PROFILE=private`)

> Owner / internal use. Mobile reaches backend-only features via the **Tailscale Desktop Bridge**; Ollama / n8n run desktop-local.

- [ ] Complete **all** of Section 1
- [ ] `DEPLOYMENT_PROFILE=private` set and confirmed on `/health`
- [ ] Desktop backend + local Postgres running; two-way Supabase sync configured
- [ ] Tailscale bridge reachable from phone (e.g. `tailscale_serve` HTTPS); `connection_mode` per integration set to `local_desktop` / `tailscale_private` / `tailscale_serve` / `auto`
- [ ] Ollama online **only** if `GET /api/tags` on the resolved endpoint responds; AI Chat inference resolves URL via the same resolver (localhost fallback only for `local`/`auto`; `tailscale` mode with no URL → honest unavailable)
- [ ] n8n online **only** if a safe health/base GET responds (no workflow execution)
- [ ] API-key AI providers (OpenAI, Claude, Gemini, Grok, Blackbox, Cursor, DeepSeek, Qwen, OpenRouter) independent of Tailscale; saving a key = **Configured**, Online needs a real **Test Connection**
- [ ] **Supabase-direct mobile** features work without backend: Tasks, Task checklist, Notes, Finance, Routines (incl. recurrence expansion), Approvals (proposals), AI Memory (suggestions), Auth (register via `provision_me` + login)
- [ ] **Backend-only mobile** features (Drive, AI Knowledge upload, Settings/Integrations/AI-provider config, n8n, Google, System control, AI Chat inference) show the reusable `SetupRequiredState` (`frontend/components/SetupRequiredState.tsx`) when the bridge is unreachable — **not** a "use desktop app" message
- [ ] `DesktopBridgePanel` shows deployment mode + needs-bridge vs no-bridge matrix + mobile setup checklist
- [ ] Distribute APK to owner device(s) only
- [ ] Reference: `docs/v4/TAILSCALE_SETUP.md`, `docs/v4/MOBILE_PARITY_QA.md`

---

## 3. Profile B — client_portal hosted launch (`DEPLOYMENT_PROFILE=client_portal`)

> Hosted / multi-tenant. Clients are **NOT** prompted to connect a desktop bridge; secrets are server-side; workspace isolation via Supabase RLS.

- [ ] Complete **all** of Section 1
- [ ] `DEPLOYMENT_PROFILE=client_portal` set and confirmed on `/health`
- [ ] **Migrations 0016 + 0017 applied to the hosted Supabase** (Section 1.4) — confirmed, since clients rely on standalone register + two-way proposal/suggestion sync
- [ ] Email confirmation decision made (Section 1.5) and communicated to clients (instant register vs confirm-email-then-login)
- [ ] Clients are **not** prompted to connect a desktop bridge
- [ ] All secrets server-side; service-role key never reaches the client bundle
- [ ] Supabase **RLS workspace isolation** verified (`app_user_id()`, `is_member()`); cross-workspace access denied
- [ ] **Funnel stays OFF**; raw Ollama / n8n not publicly exposed
- [ ] Hosted frontend build deployed (web `npm run build`); version `v4.0.0` visible on login / sidebar / Settings
- [ ] If an APK is offered to clients, it carries `v4.0.0` and points at the hosted backend
- [ ] Reference: `docs/v4/V4_RELEASE_PLAN.md`, `docs/v4/VERSIONING_AND_DOWNLOADS.md`

---

## 4. Known limitations (acknowledge before sign-off)

- [ ] n8n automations sub-section shows a plain error (not the full `SetupRequiredState`) when n8n unreachable — minor polish
- [ ] On-device pixel / emulator QA **not performed** (static + dev-runtime checks only)
- [ ] Routine **alarms / background scheduler not implemented** (no fake execution)
- [ ] Migrations 0016 / 0017 must be applied to Supabase (see Section 1.4) before relying on them

---

## 5. Artifacts (Phase 7)

- [ ] `release/v4.0.0/AllHaven-v4.0.0-source.zip` (source, no secrets)
- [ ] Master archive branch refreshed to "AllHaven 4.0"
- [ ] Android APK published to the **mobile-latest** release via `android-apk.yml`
- [ ] Version visible in app + artifact filenames include `v4.0.0`

---

## Sign-off

| Role | Name | Date | OK |
|---|---|---|---|
| Release owner | | | ☐ |
| Backend (tests/migrations) | | | ☐ |
| Frontend (build/version) | | | ☐ |
| Security review | | | ☐ |
