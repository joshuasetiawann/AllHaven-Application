# AllHaven v4.0.0 — Mobile Parity & QA

**Version:** 4.0.0 · **Branch:** `main` · **Commit:** `786b94e`
**Scope:** Mobile (Capacitor Android APK) feature parity with the desktop web app, plus the QA actually performed for this release.

> **Honesty note on QA depth.** The mobile QA in this release is **static analysis + dev-runtime checks only**. It is **not** on-device or emulator pixel/layout QA. We audited Tailwind responsive classes against breakpoints and smoke-tested live routes/assets in the running dev server. Real-device visual verification (touch targets, safe areas, keyboard overlap, actual rendered pixels at each width) has **not** been done — see [Mobile limitations](#mobile-limitations).

---

## 1. Mobile parity rules

These are the rules the v4 mobile build is held to:

1. **Every active feature is reachable on mobile.** The mobile nav (`frontend/components/layout/nav.ts`) exposes **all active modules** — nothing is hidden behind a desktop-only gate.
2. **No "use the desktop app" dead ends.** A feature that needs a connection shows an actionable **setup-required** state that explains *what* is needed and *how* to connect — never a message telling the user to go use the desktop app.
3. **Secrets are backend-only.** API keys, the Supabase service-role key, and integration credentials live server-side, encrypted at rest. They are **never** shipped in the frontend bundle or written to `localStorage`. Mobile authenticates with a Supabase Auth bearer token; it never holds privileged secrets.

### Active modules in the mobile nav

All present, none hidden, **no Weather**:

`Dashboard` · `AI Chat` · `Routine` · `Tasks` · `Finance` · `Notes` · `Approvals` · `Calculator` · `Clock` · `Drive` · `Automations` · `AI Knowledge` · `AI Memory` · `Settings`

### Weather

Weather is **removed from active scope** in v4.0.0. Active-code grep for weather is empty; `/dashboard/weather` returns **404**. The `weather_locations` table + its migrations (0004/0012/0013) + ORM model + sync entry are **kept dormant** (dropping the table would be destructive). Details: [`docs/v4/WEATHER_REMOVAL_REPORT.md`](./WEATHER_REMOVAL_REPORT.md).

---

## 2. `SetupRequiredState` behavior

`frontend/components/SetupRequiredState.tsx` is the **reusable** component shown wherever a feature can't run because a connection is missing. It replaces both raw errors and the old "use the desktop app" copy.

**Props**

| Prop | Type | Purpose |
|---|---|---|
| `feature` | `string` | Feature name, used in the heading/body. |
| `needs` | `"backend" \| "bridge"` (default `"backend"`) | Whether it needs the backend reachable or the Tailscale Desktop Bridge. |
| `reason` | `string?` | Optional custom explanation. |
| `onRetry` | `() => void?` | Optional retry handler (renders a Retry button). |

**What it renders**

- Heading: `"{feature} needs a connection"`.
- A plain-language reason (defaults differ for `backend` vs `bridge`).
- A **"What you need"** checklist:
  - `bridge`: Tailscale on this device + desktop on the same tailnet; set the service's Connection mode to **Tailscale Private** and Test it.
  - `backend`: the backend reachable (locally, or over Tailscale from mobile); then the feature works the same as desktop.
- A primary CTA linking to **Settings → Desktop Bridge** (`/dashboard/settings?tab=tools`), plus an optional **Retry**.

**How "unreachable" is detected** — `frontend/lib/connection.ts`:

- `isBackendUnreachable(err)` returns `true` for `ApiException` codes `UNAVAILABLE_ON_MOBILE` / `BRIDGE_REQUIRED`, for network/gateway statuses (`0`, `502`, `503`, `504`), and for network-ish error messages.
- `pingBackend(timeoutMs = 4000)` does a best-effort `GET /health` with a short timeout.

**Former "use desktop" message** — the one remaining instance (routine AI generation) now returns a **`BRIDGE_REQUIRED`** setup message routed through `SetupRequiredState`. **No user-facing "use desktop app" text remains.**

---

## 3. Per-module mobile status

Two ways a module works on mobile:

- **Supabase-direct** — works on mobile **without the backend** (talks straight to Supabase).
- **Backend-only** — needs the backend/bridge reachable (e.g. via Tailscale); otherwise shows `SetupRequiredState`.

| Module | Mobile mode | Notes |
|---|---|---|
| Auth (register/login) | Supabase-direct | Register via `provision_me` RPC + Supabase login. |
| Dashboard | Supabase-direct | Reachable in nav. |
| Tasks | Supabase-direct | Incl. task checklist. |
| Notes | Supabase-direct | |
| Finance | Supabase-direct | |
| Routine | Supabase-direct | Incl. recurrence expansion. |
| Approvals | Supabase-direct | Tool proposals. |
| AI Memory | Supabase-direct | Memory suggestions. |
| Calculator | Client-side | No backend needed. |
| Clock | Client-side | No backend needed. |
| AI Chat (inference) | Backend-only | Inference runs server-side / via the bridge. |
| Drive | Backend-only | |
| AI Knowledge (upload) | Backend-only | |
| Automations (n8n) | Backend-only | See limitation below re: error polish. |
| Settings / Integrations / AI-provider config | Backend-only | Secrets stay server-side. |
| Google · System control | Backend-only | |

When any **backend-only** module's backend is unreachable, the user gets `SetupRequiredState`, **not** a "use desktop" message.

---

## 4. Viewport QA done

### 4a. Static responsive-class audit

Audited Tailwind responsive classes against the three target widths:

| Width | Target | Result |
|---|---|---|
| **375px** | small phone | static class audit passed |
| **430px** | large phone | static class audit passed |
| **768px** | tablet / breakpoint | static class audit passed |

This confirms responsive class usage at these breakpoints **by source inspection**. It does **not** confirm rendered pixels on a device.

### 4b. Dev-runtime route smoke (running dev server)

| Check | Expected | Result |
|---|---|---|
| All 15 active dashboard routes | `200` | ✅ all 200 |
| `/dashboard/weather` | `404` | ✅ 404 |
| `layout.css` | `200` | ✅ css 200 |
| Weather asset / route | not served as active | ✅ weather 404 |

### 4c. Build / type checks

- Backend pytest: **471 passed** (deterministic, `-p no:randomly`).
- Frontend: `tsc` **0 errors**; web build and `build:mobile` compile (**21 routes**). `build:mobile` self-cleans its `.next` so it can't contaminate the web CSS.

---

## 5. Mobile limitations

- **No on-device / emulator pixel QA.** All mobile QA here is static-class + dev-runtime; rendered layout, touch targets, safe-area insets, and keyboard behavior on a real device are **unverified**.
- **n8n sub-section error polish.** The n8n area of the Automations page shows a **plain error** (not the full `SetupRequiredState`) when n8n is unreachable. Minor polish item.
- **Supabase migrations pending.** `0016_provision_me` and `0017_proposal_sync_fields` are **not yet applied** to hosted Supabase. Until `0016` is applied, mobile register fails with *"Could not find the function public.provision_me in the schema cache."* `0017` is needed for two-way LWW convergence of proposals/suggestions (approve/reject converging desktop↔mobile and failed approvals staying visible).
  - Apply via: `cd backend && ALLHAVEN_DB_TARGET=supabase DATABASE_URL=<supabase> alembic upgrade head` — or paste `docs/deploy/provision_me.sql` in the Supabase SQL editor for `0016`.
- **Supabase email confirmation is ON** (`mailer_autoconfirm=false`). For instant register, disable it (Auth → Providers → Email); otherwise the flow is register → confirm-email → login.
- **No routine alarms / background scheduler.** Not implemented — there is **no fake execution**.

---

*See also: [`docs/v4/V4_FEATURE_AUDIT.md`](./V4_FEATURE_AUDIT.md), [`docs/v4/WEATHER_REMOVAL_REPORT.md`](./WEATHER_REMOVAL_REPORT.md), [`docs/v4/TAILSCALE_SETUP.md`](./TAILSCALE_SETUP.md).*
