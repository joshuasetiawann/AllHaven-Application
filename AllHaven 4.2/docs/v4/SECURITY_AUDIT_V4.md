# AllHaven v4.0.0 — Security Audit

**Repo:** `joshuasetiawann/AllHaven-Application` · **Branch:** `main` · **Commit:** `786b94e`
**Version:** 4.0.0 (`VERSION`, root + `frontend` `package.json`, `frontend/components/layout/nav.ts` `APP_VERSION="v4.0.0"`, `backend/app/core/version.py`, `GET /api/v1/health`)
**Type:** Local-first AI command center web app — Next.js 14 frontend + FastAPI backend + local Postgres, two-way Supabase sync, Capacitor Android APK.

This document records the v4.0.0 security posture from the Phase 6 QA + security loop. It contains **no real secrets or credentials**.

---

## 1. Summary

| Area | Posture |
| --- | --- |
| Secret storage | Backend-only, encrypted at rest, never in frontend bundle or `localStorage` |
| `.env` tracking | No `.env` tracked (gitignored); only `.env.example` placeholders committed |
| Desktop auth/session | HttpOnly cookie + CSRF on REST |
| Mobile auth/session | Supabase Auth bearer token |
| Workspace isolation | Supabase RLS via `app_user_id()` / `is_member()` |
| Tailscale Funnel | Off by default; explicit confirm required to expose |
| Raw Ollama / n8n | Never public by default; reached via Desktop Bridge resolver |
| Secret scan | **Clean** (no real secrets in source/artifact) |

---

## 2. Secret handling

- **Backend-only.** API-provider keys, integration credentials, and the Supabase **service role key** live only in backend config / the encrypted secret store. None are bundled into the frontend or written to `localStorage`.
- **Encrypted at rest** using the local MVP encryption scheme (suitable for the local-first / private deployment profile).
- **No `.env` tracked.** `.env` is gitignored; only `.env.example` (placeholders only) is committed.
- **Provider keys never leave the backend.** Saving a key marks a provider **Configured**; turning it **Online** requires a real **Test Connection** — the key value is never echoed back to the client.

**Checklist**

- [x] Secrets stored backend-only, encrypted at rest
- [x] No secret value reaches the frontend bundle or `localStorage`
- [x] Supabase service role key is backend-only
- [x] No `.env` tracked in git; `.env.example` is placeholders only

---

## 3. Authentication & session

| Surface | Mechanism | Notes |
| --- | --- | --- |
| Desktop (REST) | HttpOnly cookie + CSRF | Session cookie not readable by JS; CSRF protection on state-changing REST calls |
| Mobile (Supabase-direct) | Supabase Auth bearer | Register via `provision_me` RPC + login; bearer token used for Supabase-direct modules |
| Data isolation | Supabase RLS | Per-workspace isolation enforced by `app_user_id()` and `is_member()` |

- **RLS workspace isolation** is the authority boundary for all Supabase-direct data (Tasks, Notes, Finance, Routines, Approvals, AI Memory). A user only sees rows in workspaces where `is_member()` holds.
- In the **`client_portal`** deployment profile, multi-tenant isolation relies on this same RLS — secrets stay server-side and clients are never prompted to connect a desktop bridge.

---

## 4. Tailscale / Desktop Bridge / Funnel risk posture

Desktop-local services (Ollama, n8n) are resolved by `backend/app/services/connection_resolver.py` (pure, no I/O) from a `connection_mode`:

`local_desktop` · `tailscale_private` · `tailscale_serve` · `tailscale_funnel` · `auto`

**Funnel = public exposure. Default OFF.**

| Guarantee | Behavior |
| --- | --- |
| Funnel default | `funnel_enabled` defaults `false` |
| Funnel without opt-in | Resolver returns **no URL** for `funnel_mode` unless explicitly enabled |
| `auto` mode | **Never** uses funnel |
| Raw Ollama / n8n | Never exposed publicly by default; reached only via the resolved bridge endpoint |
| Ollama "online" | Only if `GET /api/tags` on the resolved endpoint responds |
| n8n "online" | Only if a safe health/base `GET` responds — **no workflow execution** is triggered for health checks |

- **Honest unavailability (Phase 5).** `OllamaProvider` chat inference resolves its URL via the **same** resolver. `localhost` fallback applies **only** to `local`/`auto`; a `tailscale` mode with no URL yields an honest "unavailable" — never a fabricated response.
- **API-key AI providers are independent of Tailscale.** OpenAI, Claude, Gemini, Grok, Blackbox, Cursor, DeepSeek, Qwen, OpenRouter do not use the resolver — a test asserts `ai_provider_router` never imports it.
- **UI surfaces the risk.** `IntegrationConfigModal` renders `connection_mode` as a dropdown and `funnel_enabled` as a checkbox with a **red public-exposure warning**. `frontend/components/settings/DesktopBridgePanel.tsx` shows deployment mode, the needs-bridge vs no-bridge matrix, the mobile setup checklist, and the Funnel warning.

**Deployment profiles** (`DEPLOYMENT_PROFILE`, default `private`, exposed via `/health`):

| Profile | Public exposure | Funnel |
| --- | --- | --- |
| `private` | Owner/internal; mobile via Tailscale bridge; Ollama/n8n desktop-local | n/a |
| `client_portal` | Hosted/multi-tenant; secrets server-side; RLS isolation; no client bridge prompt | n/a |
| `public_demo` | Temporary public preview | Optional, **OFF by default + explicit confirm** |

---

## 5. File upload safety

- **AI Knowledge upload and Drive are backend-only.** On mobile they require the backend/bridge reachable; when unreachable they render the reusable `SetupRequiredState` (`frontend/components/SetupRequiredState.tsx`) rather than processing files client-side.
- File handling therefore occurs server-side under the backend's validation, never directly against a public surface in the default `private` profile.

---

## 6. API-provider key safety

- Keys for all API-based AI providers are stored backend-only and encrypted at rest (see §2).
- Provider routing (`ai_provider_router`) is **decoupled from Tailscale** — no resolver import — so a provider key's reachability/health is independent of bridge/funnel state.
- **Configured ≠ Online:** a saved key is `Configured`; `Online` requires a successful **Test Connection**. No key is returned to the client to re-test.

---

## 7. Secret-scan result

**Result: CLEAN.** No real secrets or credentials found in tracked source or in the release artifact.

- `.env` files are gitignored and untracked; only `.env.example` placeholders are committed.
- Release source archive `release/v4.0.0/AllHaven-v4.0.0-source.zip` is published **without secrets**.
- Service role key and provider keys exist only in backend runtime config, never in the repo or frontend.

**Verification (see §9 for full commands):**

```bash
# No tracked .env (expect: empty)
git ls-files | grep -E '(^|/)\.env$'

# Placeholders only present (expect: .env.example)
git ls-files | grep -E '\.env\.example'
```

---

## 8. Known remaining risks

| # | Risk | Status / mitigation |
| --- | --- | --- |
| 1 | Encryption is the **local MVP scheme** | Adequate for `private`/local-first; harden before broad hosted/multi-tenant use |
| 2 | Supabase **migrations 0016/0017 not yet applied** | Must be applied before relying on standalone mobile register + two-way proposal/suggestion sync (see below) |
| 3 | Supabase **email confirmation is ON** (`mailer_autoconfirm=false`) | Disable for instant register (Auth → Providers → Email), else register → confirm-email → login |
| 4 | n8n automations sub-section shows a plain error (not full `SetupRequiredState`) when n8n unreachable | Minor polish only |
| 5 | On-device pixel/emulator QA **not performed** | Static + dev-runtime checks only |
| 6 | Routine alarms / background scheduler **not implemented** | No fake execution; deferred |

**Pending Supabase migrations (apply before relying on them in hosted Supabase):**

- `0016_provision_me` — `SECURITY DEFINER provision_me()` RPC for standalone mobile registration (creates profile + workspace + owner membership, idempotent, adopts same-email profile). Without it, mobile register fails with *"Could not find the function public.provision_me in the schema cache"*.
- `0017_proposal_sync_fields` — adds `updated_at` + `error_message` to `ai_tool_proposals` and `updated_at` to `ai_memory_suggestions` plus a `set_updated_at` trigger; makes proposals/suggestions two-way LWW-synced so approve/reject converges desktop ↔ mobile and failed approvals stay visible.

Apply:

```bash
cd backend && ALLHAVEN_DB_TARGET=supabase DATABASE_URL=<supabase> alembic upgrade head
# OR for 0016 only: paste docs/deploy/provision_me.sql in the Supabase SQL editor
```

---

## 9. Verification commands

**Secrets / `.env` hygiene**

```bash
# No tracked .env (expect: empty output)
git ls-files | grep -E '(^|/)\.env$'

# Placeholders only (expect: .env.example)
git ls-files | grep -E '\.env\.example'

# .env is ignored
git check-ignore .env
```

**Tailscale / bridge independence**

```bash
# Funnel-off-by-default, honest unreachable gating, Ollama-chat-via-bridge,
# API-provider independence from the resolver
cd backend && pytest tests/test_desktop_bridge.py -p no:randomly -q

# Full backend suite (expect: 471 passed)
cd backend && pytest -p no:randomly -q
```

**Version / health (deployment profile + env surfaced)**

```bash
# version endpoint + cross-source consistency
cd backend && pytest tests/test_version.py -p no:randomly -q

# health exposes app_version + deployment_profile + env
curl -s http://localhost:8000/api/v1/health
```

**Frontend integrity**

```bash
cd frontend && npx tsc --noEmit          # expect: 0 errors
cd frontend && npm run build             # web build
cd frontend && npm run build:mobile      # self-cleans its own .next so it can't contaminate web CSS
```

---

*Generated for the AllHaven v4.0.0 release (Phase 6 QA + security loop).*
