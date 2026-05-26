# AllHaven v4.0.0 — Release Plan

**Version:** 4.0.0
**Branch:** `main` · **Latest commit:** `786b94e`
**Repo:** `joshuasetiawann/AllHaven-Application`

AllHaven is a **local-first AI command center web app** — a Next.js 14 frontend, a FastAPI backend, a local PostgreSQL database with two-way Supabase sync, and a Capacitor-built Android APK for mobile. It is an application, **not a real operating system**.

---

## 1. v4.0 Goals

v4.0 turns AllHaven into an **honest, deployable** product across desktop and mobile:

- **Mobile parity.** Mobile exposes every active module the desktop has — nothing is hidden, nothing is faked.
- **Honest gating.** Features that genuinely need the backend say so clearly (a reusable setup state), instead of a dishonest "use the desktop app" dead end or a fabricated success response.
- **Tailscale Desktop Bridge.** Desktop-local services (Ollama, n8n) become reachable from mobile over Tailscale through a single, pure URL resolver — without exposing anything to the public internet by default.
- **Deployment profiles.** One codebase serves the private owner, a hosted multi-tenant client portal, and a temporary public demo, each with appropriate defaults.
- **Version visibility.** `v4.0.0` is consistent and visible across every source of truth and in the running app.
- **Scope cleanup.** The dormant Weather feature is removed from active scope without destructive data loss.

---

## 2. Phases Delivered

All seven phases (0–6) are committed and pushed.

| Phase | Name | What it delivered |
|-------|------|-------------------|
| **0** | Audit + Decisions | Full audit of the app; recorded the key architecture decisions (below) that gate every later phase. |
| **1** | Weather removal + version bump | Removed Weather from active scope; bumped every version source of truth to `4.0.0`. |
| **2** | Mobile parity + setup-required states | Mobile nav exposes all active modules; unreachable backend features render a reusable `SetupRequiredState` instead of "use desktop". |
| **3** | Tailscale Desktop Bridge + deployment profiles | Pure `connection_resolver` by `connection_mode`; bridge fields on Ollama/n8n; `DEPLOYMENT_PROFILE`; bridge UI. |
| **4** | Version visibility | `v4.0.0` surfaced on login, sidebar, Settings header, and `/api/v1/health`. |
| **5** | Feature repair | Ollama **chat inference** now routes through the same resolver; honest unavailability when no URL resolves. |
| **6** | QA + security loop | Test suites, route smoke checks, and a security pass; caught and removed 2 residual active Weather references. |

### Phase detail

**Phase 0 — Audit + Decisions.** Established the four architecture decisions (deployment profiles, Tailscale bridge, mobile parity via setup-states, honest gating) that constrain the rest of the release. See the Phase 0 checkpoint below.

**Phase 1 — Weather removal + version bump.** Weather was dormant and removed from active scope; version bumped to `4.0.0` across all sources (see §4).

**Phase 2 — Mobile parity + setup-required states.** `frontend/components/layout/nav.ts` now lists every active module on mobile. Backend-only features fall back to `frontend/components/SetupRequiredState.tsx`. `frontend/lib/connection.ts` adds `isBackendUnreachable()` and `pingBackend()`.

**Phase 3 — Tailscale Desktop Bridge + deployment profiles.** `backend/app/services/connection_resolver.py` (pure, no I/O) resolves a desktop-local service URL by `connection_mode`. Ollama/n8n configs gain bridge fields; the bridge UI (`IntegrationConfigModal`, `frontend/components/settings/DesktopBridgePanel.tsx`) makes mode and exposure explicit. `DEPLOYMENT_PROFILE` introduced.

**Phase 4 — Version visibility.** `GET /api/v1/health` returns `app_version`, `deployment_profile`, and `env`; the version is shown in the UI.

**Phase 5 — Feature repair (Ollama chat via bridge).** `OllamaProvider` chat inference resolves its URL via the same resolver. Localhost fallback applies **only** to `local`/`auto` modes; a tailscale mode with no URL returns honest unavailability — no fake response. API-key AI providers are independent of the resolver.

**Phase 6 — QA + security loop.** Backend pytest, frontend `tsc`/build, route smoke tests, and a security pass. This phase found and removed the last 2 active Weather references (commit `786b94e`).

---

## 3. Key Architecture Decisions

### 3.1 Deployment profiles

`DEPLOYMENT_PROFILE` config (default `private`), exposed via `/health`:

| Profile | Use | Behavior |
|---------|-----|----------|
| `private` | Owner / internal | Mobile reaches desktop via the Tailscale bridge; Ollama and n8n are desktop-local. |
| `client_portal` | Hosted / multi-tenant | Clients are **not** prompted to connect a desktop bridge; secrets live server-side; workspace isolation via Supabase RLS. |
| `public_demo` | Temporary public preview | Funnel optional, **OFF by default**, requires explicit confirmation. |

### 3.2 Tailscale Desktop Bridge

`backend/app/services/connection_resolver.py` is a **pure** resolver (no I/O) that maps a desktop-local service to a URL by `connection_mode`:

`local_desktop` · `tailscale_private` · `tailscale_serve` · `tailscale_funnel` · `auto`

Ollama and n8n integration configs (in the provider registry / JSON config — **no migration**) gained bridge fields: `connection_mode`, `tailscale_url`, `serve_url`, `funnel_url`, `funnel_enabled`.

**Resolve-then-test, honestly:**
- **Ollama is online only** if `GET /api/tags` on the resolved endpoint responds.
- **n8n is online only** if a safe health/base `GET` responds — **no workflow execution**.

**Funnel safety:**
- `funnel_enabled` defaults to `false`.
- The resolver returns **no URL** for funnel mode unless funnel is explicitly enabled.
- `auto` never selects funnel.

**UI:** `IntegrationConfigModal` renders `connection_mode` as a dropdown and `funnel_enabled` as a checkbox with a red public-exposure warning. `DesktopBridgePanel.tsx` shows the deployment mode, a needs-bridge vs. no-bridge matrix, a mobile setup checklist, and the Funnel warning.

**API-key providers are independent.** OpenAI, Claude, Gemini, Grok, Blackbox, Cursor, DeepSeek, Qwen, and OpenRouter do **not** touch the resolver — a test asserts `ai_provider_router` never imports it. Saving a key = **Configured**; **Online** still requires a real Test Connection.

### 3.3 Mobile parity via setup-states

Mobile nav includes **all** active modules: Dashboard, AI Chat, Routine, Tasks, Finance, Notes, Approvals, Calculator, Clock, Drive, Automations, AI Knowledge, AI Memory, Settings. No Weather, nothing hidden.

**Works without a backend (Supabase-direct on mobile):**
- Tasks · Task checklist · Notes · Finance · Routines (incl. recurrence expansion) · Approvals (proposals) · AI Memory (suggestions) · Auth (register via `provision_me` RPC + login)

**Needs the backend reachable (e.g. via Tailscale):**
- Drive · AI Knowledge upload · Settings / Integrations / AI-provider config · n8n · Google · System control · AI Chat inference

### 3.4 Honest gating

- When the backend/bridge is unreachable, backend-only features render the reusable `SetupRequiredState` — **not** a "use desktop app" message.
- The former routine AI-generation "use desktop" message now returns a `BRIDGE_REQUIRED` setup message.
- **No user-facing "use desktop app" text remains** anywhere.

---

## 4. Version Consistency

`VERSION = 4.0.0` is the single source, referenced everywhere:

- [x] `VERSION` file
- [x] root `package.json`
- [x] `frontend/package.json`
- [x] `frontend/components/layout/nav.ts` → `APP_VERSION = "v4.0.0"`
- [x] `backend/app/core/version.py` → `get_app_version()` reads `VERSION`
- [x] `GET /api/v1/health` → returns `app_version`, `deployment_profile`, `env`
- [x] Visible on the login screen, the sidebar, and the Settings header

---

## 5. Weather Removal (active scope)

Weather is removed from active scope. The active-code grep for "weather" is **empty**; `/dashboard/weather` returns **404**. See `docs/v4/WEATHER_REMOVAL_REPORT.md`.

**Deleted:**
- Backend: `routers/weather.py`, `schemas/weather.py`, `services/weather_service.py`
- Config: `WEATHER_API_KEY`, `WEATHER_PROVIDER`; `.env.example` keys; the `env_file_service` allowlist entry
- `integration_status_service` "Weather API" card
- Frontend: `weatherApi` (`apiRest` + `apiSupabase`); `WeatherLocation` / `WeatherCurrent` types

**Kept (dormant, documented — dropping the table is destructive):**
- `weather_locations` table + migrations `0004` / `0012` / `0013` + ORM model + sync entry

---

## 6. Tests & Quality

**Backend:** `pytest` — **471 passed** (deterministic, `-p no:randomly`).

| New v4 test file | Coverage |
|------------------|----------|
| `tests/test_version.py` | Version endpoint + cross-source consistency |
| `tests/test_desktop_bridge.py` | 13 tests: resolver by mode, funnel-off-by-default, honest Ollama/n8n unreachable gating, Ollama-chat-via-bridge, API-provider independence |
| `tests/test_ai_intent_finance.py` | 33 tests (from v3.9): finance-first intent + memory gating |

**Frontend:** `tsc` 0 errors; web build and `build:mobile` compile (21 routes). `build:mobile` now self-cleans its `.next` so it can't contaminate the web CSS.

**Route smoke:** all 15 active dashboard routes serve 200; `/dashboard/weather` 404; `layout.css` 200.

---

## 7. Security

- Secrets are **backend-only**, encrypted at rest (local MVP scheme); never in the frontend bundle or `localStorage`. Service role key is backend-only.
- No `.env` is tracked (gitignored); `.env.example` holds placeholders only.
- Funnel is **off by default**; raw Ollama/n8n is never exposed publicly by default.
- Auth: HttpOnly cookie + CSRF on the desktop REST API; mobile uses Supabase Auth bearer.
- RLS workspace isolation via `app_user_id()` / `is_member()`.

---

## 8. Release Scope & Artifacts (Phase 7)

- `release/v4.0.0/AllHaven-v4.0.0-source.zip` — source, no secrets.
- Master archive branch refreshed to "AllHaven 4.0".
- Android APK built via the existing GitHub Actions `android-apk.yml` (Capacitor) → published to the `mobile-latest` release.
- Version is visible in-app and artifact filenames include `v4.0.0`.

---

## 9. Required: Pending Supabase Migrations

**The user must apply these before relying on the hosted-Supabase features they enable.**

| Migration | Adds | Why it matters |
|-----------|------|----------------|
| `0016_provision_me` | `SECURITY DEFINER provision_me()` RPC | Standalone mobile registration: creates profile + workspace + owner membership; idempotent; adopts a same-email profile. **Without it, mobile register fails:** `Could not find the function public.provision_me in the schema cache`. |
| `0017_proposal_sync_fields` | `updated_at` + `error_message` on `ai_tool_proposals`; `updated_at` on `ai_memory_suggestions`; a `set_updated_at` trigger | Makes proposals/suggestions two-way LWW-synced, so approve/reject converges desktop ↔ mobile and failed approvals stay visible. |

**Apply via:**

```bash
cd backend && ALLHAVEN_DB_TARGET=supabase DATABASE_URL=<supabase> alembic upgrade head
```

— or, for `0016` only, paste `docs/deploy/provision_me.sql` into the Supabase SQL editor.

**Supabase Auth note:** the project currently has email confirmation **ON** (`mailer_autoconfirm=false`). Disable it (Auth → Providers → Email) for instant register; otherwise the flow is register → confirm-email → login.

---

## 10. Known Limitations

- The n8n automations sub-section shows a plain error (not the full `SetupRequiredState`) when n8n is unreachable — minor polish.
- On-device pixel/emulator QA was **not** performed (static + dev-runtime checks only).
- Migrations `0016` / `0017` are **not yet applied** to Supabase.
- Routine alarms / background scheduler are **not implemented** (no fake execution).

---

## Appendix A — Phase 0 Checkpoint Decisions

Recorded at the Phase 0 audit; these gate all later phases:

1. **Deployment profiles.** Ship one codebase with a `DEPLOYMENT_PROFILE` of `private` | `client_portal` | `public_demo` (default `private`), each with appropriate defaults, surfaced via `/health`.
2. **Tailscale Desktop Bridge.** Reach desktop-local services (Ollama, n8n) from mobile through a single **pure** URL resolver keyed by `connection_mode`; never expose them publicly by default; Funnel is opt-in and off by default.
3. **Mobile parity via setup-states.** Expose every active module on mobile; gate backend-only features behind a reusable `SetupRequiredState` rather than hiding them.
4. **Honest gating.** Remove every "use the desktop app" dead end and every fabricated success; unavailable features must tell the truth (`BRIDGE_REQUIRED` / setup-required) and online status must reflect a real check.
5. **Weather out of active scope.** Remove Weather from active code but **keep** its table and migrations (dropping the table is destructive).
