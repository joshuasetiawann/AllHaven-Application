# AllHaven v4.0.0 — Release Notes

**Full Mobile Parity + Tailscale Bridge + Release-Grade Stability**

AllHaven is a local-first AI command center — a **web app** (Next.js 14 frontend + FastAPI backend + local Postgres with two-way Supabase sync), packaged as an Android APK via Capacitor. It is not a real operating system; the "command center" framing is just the UI metaphor.

This is a big one. v4.0.0 closes the gap between desktop and mobile, adds an honest way to reach your desktop-only AI services (Ollama, n8n) from your phone over Tailscale, introduces deployment profiles for different audiences, removes the dormant Weather feature, and makes the running version visible everywhere. The v3.9 AI fixes ride along too.

---

## TL;DR

| Area | What changed |
| --- | --- |
| **Mobile** | Every active module now appears on mobile — nothing hidden. Features that genuinely need the backend show a friendly **Setup Required** state instead of "use the desktop app." |
| **Tailscale Desktop Bridge** | Reach desktop-local Ollama / n8n from your phone via Tailscale. Public **Funnel** exposure is **off by default**. |
| **Deployment profiles** | New `DEPLOYMENT_PROFILE` (`private` / `client_portal` / `public_demo`) tunes behavior per audience. |
| **Weather** | Removed from active scope. `/dashboard/weather` now returns 404. |
| **Version visibility** | `v4.0.0` shows on the login screen, sidebar, and Settings, and is reported by the health endpoint. |
| **AI quality (from v3.9)** | Finance-first intent routing, cross-device approval sync, and better money parsing carried in. |

---

## Full mobile parity

The mobile navigation now includes **all active modules** — the same list you see on desktop:

Dashboard · AI Chat · Routine · Tasks · Finance · Notes · Approvals · Calculator · Clock · Drive · Automations · AI Knowledge · AI Memory · Settings

No modules are hidden on mobile, and there's no Weather entry anywhere.

### Works on mobile with no backend (Supabase-direct)

These talk straight to Supabase, so they work on your phone even when your desktop/backend is asleep:

- Tasks + task checklists
- Notes
- Finance
- Routines (including recurrence expansion)
- Approvals (proposals)
- AI Memory (suggestions)
- Auth — register (via the `provision_me` RPC) and login

### Needs the backend reachable (e.g. via the Tailscale bridge)

These require your backend to be online — typically reached over Tailscale:

- Drive
- AI Knowledge upload
- Settings / Integrations / AI-provider config
- n8n, Google, system control
- AI Chat inference

When the backend or bridge isn't reachable, these screens render a **reusable Setup Required state** (`frontend/components/SetupRequiredState.tsx`) that tells you what to connect — **not** a dead-end "use the desktop app" message. The one place that used to say that (routine AI generation) now returns a clear `BRIDGE_REQUIRED` setup message instead. Connection checks live in `frontend/lib/connection.ts` (`isBackendUnreachable()` + `pingBackend()`).

---

## Tailscale Desktop Bridge

Some services run **on your desktop only** — local Ollama for AI inference and your local n8n automations. The new Desktop Bridge lets your phone reach them over your private Tailscale network.

### How it resolves a URL

`backend/app/services/connection_resolver.py` picks the right endpoint based on a per-service `connection_mode`:

| Mode | What it does |
| --- | --- |
| `local_desktop` | Plain localhost on the desktop |
| `tailscale_private` | Your private tailnet address |
| `tailscale_serve` | Tailscale Serve (HTTPS within your tailnet) |
| `tailscale_funnel` | Public Funnel — only used if **explicitly enabled** |
| `auto` | Best available — **never** uses Funnel |

The resolver is pure (no network I/O). Ollama and n8n integration configs gained bridge fields: `connection_mode`, `tailscale_url`, `serve_url`, `funnel_url`, and `funnel_enabled` (stored in the provider registry's JSON config — **no migration needed**).

### Honest online/offline status

- **Ollama** is reported online **only if** `GET /api/tags` on the resolved endpoint actually responds.
- **n8n** is reported online **only if** a safe health/base `GET` responds — no workflow execution is triggered just to check status.

### Funnel is off by default 🔒

Funnel publicly exposes a service to the internet, so:

- `funnel_enabled` defaults to **false**.
- In `funnel` mode the resolver returns **no URL** unless you've explicitly enabled it.
- `auto` mode **never** falls back to Funnel.
- The config UI (`IntegrationConfigModal`) shows `connection_mode` as a dropdown and `funnel_enabled` as a checkbox with a **red public-exposure warning**.

`frontend/components/settings/DesktopBridgePanel.tsx` shows your current deployment mode, a "needs-bridge vs no-bridge" matrix, a mobile setup checklist, and the Funnel warning.

### AI inference and API-key providers

- **Ollama chat** now resolves its URL through the same resolver. Localhost fallback applies **only** for `local`/`auto` modes; a `tailscale` mode with no URL returns an honest "unavailable" — never a fake response.
- **API-key AI providers** (OpenAI, Claude, Gemini, Grok, Blackbox, Cursor, DeepSeek, Qwen, OpenRouter) are **completely independent** of Tailscale. A test asserts the AI provider router never imports the resolver. Saving a key marks a provider **Configured**; **Online** still requires a real **Test Connection**.

---

## Deployment profiles

The new `DEPLOYMENT_PROFILE` config (default `private`) tunes AllHaven for who's using it. It's reported by the health endpoint.

| Profile | For | Behavior |
| --- | --- | --- |
| `private` | Owner / internal use | Mobile connects via the Tailscale bridge; Ollama and n8n stay desktop-local. |
| `client_portal` | Hosted / multi-tenant | Clients are **not** prompted to connect a desktop bridge; secrets stay server-side; workspace isolation via Supabase RLS. |
| `public_demo` | Temporary public preview | Funnel is optional, **off by default**, and requires explicit confirmation. |

---

## Weather removed

Weather has been removed from active scope. The active-code grep for "weather" is empty, and `/dashboard/weather` now returns **404**.

- **Deleted:** backend `routers/weather.py`, `schemas/weather.py`, `services/weather_service.py`; the `WEATHER_API_KEY` / `WEATHER_PROVIDER` config + `.env.example` keys; the env-file allowlist entry; the "Weather API" integration-status card; the frontend `weatherApi` (REST + Supabase) and `WeatherLocation` / `WeatherCurrent` types.
- **Kept (dormant, documented):** the `weather_locations` table, migrations `0004` / `0012` / `0013`, the ORM model, and its sync entry — dropping the table would be destructive, so it's left in place but unused.

Details: `docs/v4/WEATHER_REMOVAL_REPORT.md`.

---

## Version visibility

`VERSION = 4.0.0` is now consistent across the `VERSION` file, root `package.json`, `frontend/package.json`, `frontend/components/layout/nav.ts` (`APP_VERSION = "v4.0.0"`), and `backend/app/core/version.py`. `GET /api/v1/health` returns `app_version`, `deployment_profile`, and `env`. **v4.0.0** is visible on the login screen, the sidebar, and the Settings header.

---

## AI fixes carried in (from v3.9)

- **Finance-first intent routing** with proper memory gating.
- **Cross-device approval sync** — approve/reject converges between desktop and mobile, and failed approvals stay visible.
- **Better money parsing** in finance intents.

---

## ⚠️ Before you rely on hosted Supabase: apply the pending migrations

Two migrations are **not yet applied** to hosted Supabase. Mobile registration and two-way approval sync depend on them.

| Migration | What it adds | Why it matters |
| --- | --- | --- |
| `0016_provision_me` | A `SECURITY DEFINER` `provision_me()` RPC | Standalone mobile registration: creates profile + workspace + owner membership (idempotent, adopts a same-email profile). **Without it, mobile register fails** with `Could not find the function public.provision_me in the schema cache`. |
| `0017_proposal_sync_fields` | `updated_at` + `error_message` on `ai_tool_proposals`, `updated_at` on `ai_memory_suggestions`, and a `set_updated_at` trigger | Makes proposals/suggestions two-way LWW-synced so approve/reject converges desktop ↔ mobile and failed approvals stay visible. |

**How to apply:**

```bash
cd backend
ALLHAVEN_DB_TARGET=supabase DATABASE_URL=<your-supabase-url> alembic upgrade head
```

Or, for `0016` only, paste `docs/deploy/provision_me.sql` into the Supabase SQL editor.

**One more thing:** the Supabase project currently has **email confirmation ON** (`mailer_autoconfirm = false`). For instant registration, disable it under **Auth → Providers → Email**. Otherwise the flow is register → confirm email → login.

---

## Quality bar for this release

- **Backend:** `pytest` — **471 passed** (deterministic, `-p no:randomly`).
  - New in v4: `tests/test_version.py` (version endpoint + cross-source consistency), `tests/test_desktop_bridge.py` (13 tests: resolver by mode, Funnel-off-by-default, honest Ollama/n8n unreachable gating, Ollama-chat-via-bridge, API-provider independence), `tests/test_ai_intent_finance.py` (33 tests: finance-first intent + memory gating, from v3.9).
- **Frontend:** `tsc` — **0 errors**; web build and `build:mobile` both compile (21 routes).
- **Route smoke:** all 15 active dashboard routes serve **200**, `/dashboard/weather` serves **404**, `layout.css` serves **200**.

---

## Security notes

- Secrets are stored **backend-only**, encrypted at rest (local MVP scheme). They never reach the frontend bundle or `localStorage`. The service-role key is backend-only.
- No `.env` is tracked (it's gitignored); `.env.example` contains placeholders only.
- **Funnel is off by default** — raw Ollama/n8n are never exposed publicly by default.
- Auth: HttpOnly cookie + CSRF on desktop REST; mobile uses Supabase Auth bearer tokens.
- RLS workspace isolation via `app_user_id()` / `is_member()`.
- `build:mobile` now self-cleans its `.next` so it can't contaminate the web build's CSS.

---

## Known limitations

- The **n8n automations** sub-section shows a plain error (not the full Setup Required state) when n8n is unreachable — minor polish still pending.
- On-device pixel / emulator QA was **not** performed — verification was static + dev-runtime checks only.
- Migrations `0016` / `0017` are **not yet applied** to Supabase (see above).
- **Routine alarms / background scheduler** are not implemented — no fake execution is faked in their place.

---

## Artifacts

- Source archive: `release/v4.0.0/AllHaven-v4.0.0-source.zip` (source, no secrets).
- The master archive branch has been refreshed to "AllHaven 4.0".
- The Android APK is built via the existing GitHub Actions workflow `android-apk.yml` (Capacitor) and published to the `mobile-latest` release. Artifact filenames include `v4.0.0`.

---

Thanks for running AllHaven. If you're upgrading a hosted Supabase setup, do the migration step first — that's the one thing that will bite you if you skip it. Everything else should just light up.
