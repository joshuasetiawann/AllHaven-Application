# AllHaven v4.0.0 — Versioning & Downloads

This document explains how AllHaven's version is defined, where `v4.0.0` is
surfaced to users, how release artifacts are named, and how to download &
install the desktop (web) app and the mobile (Android) app.

> AllHaven is a **local-first AI command center web app** (Next.js 14 frontend +
> FastAPI backend + local Postgres, with two-way Supabase sync and a Capacitor
> Android APK). It is **not** a real operating system.

---

## 1. Version source of truth

The version is **`4.0.0`**. To prevent drift across surfaces, there is a single
canonical source — the repo-root `VERSION` file — and a consistency test that
guards every place the version appears.

### Canonical source

| Layer | Location | How it gets the version |
| --- | --- | --- |
| **Root** | `VERSION` | The single source of truth. Contains `4.0.0`. |
| **Backend** | `backend/app/core/version.py` → `get_app_version()` | Reads the repo-root `VERSION` file (`parents[3] / "VERSION"`), `lru_cache`d, safe `"0.0.0"` fallback on `OSError`. |
| **Health endpoint** | `GET /api/v1/health` | Returns `app_version` (from `get_app_version()`), plus `deployment_profile` and `env`. |
| **FastAPI app metadata** | `backend/app/main.py` | App `version=` is set from `get_app_version()`; also used in startup logging. |
| **Frontend (nav)** | `frontend/components/layout/nav.ts` | `export const APP_VERSION = "v4.0.0";` — the frontend reads its own constant (it does not call the backend just to render the badge). |
| **Package manifests** | `package.json` (root), `frontend/package.json` | `"version": "4.0.0"`. |

> Note on formatting: the `VERSION` file / backend / package manifests use the
> bare semver `4.0.0`; the frontend nav constant uses the `v`-prefixed
> `v4.0.0` for display.

### Consistency test

`backend/tests/test_version.py` verifies:

- the `/api/v1/health` (version) endpoint reports the expected version, **and**
- **cross-source consistency** — the version is the same across the canonical
  sources so the surfaces can never silently drift.

This test is part of the backend pytest suite (run deterministically with
`-p no:randomly`).

---

## 2. Where v4.0.0 shows up

Users can confirm they are on v4.0.0 from any of these surfaces:

- [ ] **Login screen** — version badge shows `v4.0.0`.
- [ ] **Sidebar** — version badge shows `v4.0.0` (from the nav `APP_VERSION` constant).
- [ ] **Settings header** — shows `v4.0.0`.
- [ ] **Health endpoint** — `GET /api/v1/health` returns JSON including
      `app_version` (= `4.0.0`), `deployment_profile`, and `env`.

Example health response shape:

```json
{
  "status": "ok",
  "app": "<app name>",
  "app_version": "4.0.0",
  "deployment_profile": "private",
  "env": "<environment>"
}
```

> `deployment_profile` is one of `private` | `client_portal` | `public_demo`
> (default `private`). It is exposed here so operators can confirm which profile
> a running instance is using.

---

## 3. Release artifact naming

| Artifact | Name | Notes |
| --- | --- | --- |
| **Desktop source bundle** | `AllHaven-v4.0.0-source.zip` | Source ZIP, **no secrets** (no tracked `.env`; `.env.example` placeholders only). Lives under `release/v4.0.0/`. |
| **Android APK** | Published to the **`mobile-latest`** GitHub release | Built via the existing GitHub Actions workflow `android-apk.yml` (Capacitor). |
| **Master archive** | **`AllHaven 4.0`** | The master archive branch refreshed to "AllHaven 4.0". |

The version is visible both **inside the app** (see §2) and in the **artifact
filenames** (`v4.0.0`).

---

## 4. Download & install — Desktop (web app)

The desktop experience is the **local-first web app** (Next.js frontend +
FastAPI backend + local Postgres, with two-way Supabase sync).

### Get the source

Download **`AllHaven-v4.0.0-source.zip`** (from `release/v4.0.0/`) and unzip it,
or clone the repository at the `v4.0.0` release.

### Launch (one-click launchers)

The repo ships one-click launchers at its root:

| OS | Launcher |
| --- | --- |
| Linux | `START_HAVEN_LINUX.sh` |
| macOS | `START_HAVEN_MAC.command` |
| Windows | `START_HAVEN_WINDOWS.bat` |

For Linux/macOS there is also `install.sh` (installs & starts from the current
terminal), and `allhaven.sh` as a setup/run helper.

### Install checklist

- [ ] Unzip `AllHaven-v4.0.0-source.zip` (or clone the repo).
- [ ] Ensure prerequisites are present (Node for the Next.js frontend, Python
      for the FastAPI backend, local Postgres).
- [ ] Run the launcher for your OS (`START_HAVEN_LINUX.sh`,
      `START_HAVEN_MAC.command`, or `START_HAVEN_WINDOWS.bat`).
- [ ] Open the app and confirm `v4.0.0` on the login screen / sidebar / Settings
      header, or hit `GET /api/v1/health`.

> **Secrets stay backend-only.** API keys and the Supabase service-role key are
> stored backend-only and encrypted at rest; they are never shipped in the
> frontend bundle, in `localStorage`, or in the source ZIP. No `.env` is
> tracked — only `.env.example` placeholders.

---

## 5. Download & install — Mobile (Android APK)

The mobile app is a **Capacitor Android build** of the same web app. It talks
**directly to Supabase** for most modules and reaches the desktop backend (over
a Tailscale bridge) for backend-only features.

### Get the APK

1. Open the project's **GitHub Releases**.
2. Select the **`mobile-latest`** release.
3. Download the **APK** asset (built by the `android-apk.yml` GitHub Actions
   workflow).

### Install checklist

- [ ] Download the APK from the **`mobile-latest`** GitHub release.
- [ ] On the Android device, allow installation from your browser/file manager
      (sideloading) if prompted.
- [ ] Install and open the APK.
- [ ] Register/login and confirm `v4.0.0` on the login screen / sidebar /
      Settings header.

### What works without a backend vs. needs the desktop bridge

| Works on mobile via **Supabase-direct** (no backend) | Needs the **desktop backend reachable** (e.g. via Tailscale bridge) |
| --- | --- |
| Tasks, Task checklist | Drive |
| Notes | AI Knowledge upload |
| Finance | Settings / Integrations / AI-provider config |
| Routines (incl. recurrence expansion) | n8n |
| Approvals (proposals) | Google |
| AI Memory (suggestions) | System control |
| Auth (register via `provision_me` RPC + login) | AI Chat inference |

> When a backend-only feature can't reach the backend/bridge, the app shows a
> reusable **`SetupRequiredState`** (not a "use the desktop app" message). There
> is no user-facing "use desktop app" text remaining.

### Before relying on hosted Supabase (operator action required)

These migrations are **pending** and must be applied by the operator before
standalone-mobile registration and two-way proposal/suggestion sync work in
hosted Supabase:

- [ ] **`0016_provision_me`** — `SECURITY DEFINER provision_me()` RPC for
      standalone mobile registration (creates profile + workspace + owner
      membership; idempotent). Without it, mobile register fails with
      *"Could not find the function public.provision_me in the schema cache"*.
- [ ] **`0017_proposal_sync_fields`** — adds `updated_at` + `error_message` to
      `ai_tool_proposals`, `updated_at` to `ai_memory_suggestions`, and a
      `set_updated_at` trigger (makes proposals/suggestions two-way LWW-synced).

Apply with:

```bash
cd backend && ALLHAVEN_DB_TARGET=supabase DATABASE_URL=<supabase> alembic upgrade head
```

(or paste `docs/deploy/provision_me.sql` into the Supabase SQL editor for 0016).

> The Supabase project currently has **email confirmation ON**
> (`mailer_autoconfirm=false`). For instant register, disable it under
> **Auth → Providers → Email**; otherwise the flow is
> register → confirm-email → login.

---

## 6. Quick reference

| Question | Answer |
| --- | --- |
| What's the version? | `4.0.0` (`v4.0.0` in the UI) |
| Where's the source of truth? | repo-root `VERSION` file |
| How does the backend read it? | `get_app_version()` in `backend/app/core/version.py` |
| Where can a user see it? | Login, sidebar, Settings header, `GET /api/v1/health` |
| Desktop artifact | `AllHaven-v4.0.0-source.zip` (under `release/v4.0.0/`) |
| Mobile artifact | APK on the **`mobile-latest`** GitHub release (`android-apk.yml`) |
| Master archive | `AllHaven 4.0` |
