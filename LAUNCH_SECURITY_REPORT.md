# AllHaven — Launch Security Report

**Version:** 0.6.0 · **Date:** 2026-06-10 · **Verdict:** ✅ Launch-ready for local-first / single-tenant use, with documented residual items below.

Scope audited: secrets, auth/session, API, database, file upload, AI tool safety,
integrations, dependencies, and HTTP security headers — across `frontend/` and `backend/`.

---

## Summary

| Area | Status |
|------|--------|
| Secrets exposure | ✅ Pass |
| Auth / private routes | ✅ Pass (token in localStorage — documented) |
| API validation & errors | ✅ Pass |
| Database scoping / injection | ✅ Pass |
| File upload | ✅ Pass (hardened this release) |
| AI tool safety | ✅ Pass (human-in-the-loop) |
| Integrations (keys server-side) | ✅ Pass |
| Security headers | ✅ Added this release |
| Dependencies | ⚠️ Critical fixed; one residual Next "high" documented |

## Fixed in this release (0.6.0)
1. **Security headers** added on every backend response (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Permissions-Policy`), and on the frontend via `next.config.js` (same set + a production **Content-Security-Policy** with `frame-ancestors 'none'`, `object-src 'none'`, no `unsafe-eval`).
2. **Drive downloads hardened**: forced `Content-Disposition: attachment` and active content types (`text/html`, `image/svg+xml`, JS/XML) are served as `application/octet-stream` — an uploaded `.html`/`.svg` can't render inline (XSS) even with a crafted content-type.
3. **Dependencies**: bumped Next `14.2.18 → 14.2.35` (fixes the **critical** middleware-authorization-bypass + many others) and forced `postcss → 8.5.15` tree-wide (fixes the moderate stringify-XSS).

## What was verified (no change needed)
- **Secrets:** no API keys in frontend code, `localStorage`, console logs, or JSON responses. Provider keys are encrypted at rest and only **masked previews** are returned. `.env` is git-ignored (never in the release ZIP); `.env.example` holds placeholders only.
- **Auth:** private routes redirect to `/login`; all data endpoints require a bearer token; clear logout clears the token + cached user.
- **API:** every request body is validated by Pydantic; centralized exception handlers return a clean error envelope and **never leak stack traces** (generic 500). CORS uses header-auth (no cookies); origins are configurable and `allow_credentials` is only set with an explicit allow-list (no wildcard-with-credentials).
- **Database:** SQLAlchemy ORM / parameterized queries throughout (no string SQL); every business query is **workspace-scoped**; deletes are soft.
- **File upload:** basename-only sanitization + `commonpath` assertions block path traversal; 25 MB cap; UUID-prefixed stored names; files live in a data dir and are never executed.
- **AI safety:** the AI **proposes, humans approve** — no autonomous writes; honest "not configured/unsupported" statuses (no fabricated output); uploaded images are sent only to vision-capable providers; an external-AI privacy warning shows before sending to external models.
- **Integrations:** Supabase service-role key, Google client secret, n8n key, and all model-provider keys are **server-side only** (encrypted DB + allow-listed `.env` mirror); never shipped to the browser.

---

## Residual risks (documented, not launch-blocking for local-first)

1. **Next.js residual "high" (npm audit).** A bundle of Next DoS / cache-poisoning / SSRF advisories (affected `9.5.0–15.5.15`) is only fully cleared by upgrading to **Next 16** — a breaking change that also requires **React 19** and a full migration + retest. We stayed on the latest **14.2.x** (critical bypass fixed). **Exposure is low for this app** because the affected features are **not used**: no `next/image` Optimizer (`remotePatterns`), no Next **middleware**, no **rewrites/i18n**, no **Server Actions** (all writes go through FastAPI), no CSP-nonce/`beforeInteractive` scripts; and it's **local-first** (single-tenant). *Recommendation:* schedule a Next 16 / React 19 upgrade as a dedicated follow-up.
2. **Auth token in `localStorage`.** Standard SPA pattern; readable by XSS. Mitigated by the new CSP + nosniff + the app not rendering untrusted HTML. *Recommendation for a hosted multi-user launch:* move to httpOnly + SameSite cookies (backend session) — a deliberate change, out of scope here.
3. **Rate limiting** is not implemented in-app (suited to a reverse proxy / gateway). *Recommendation:* add gateway rate limits (esp. on `/auth/*`) for a public deployment.
4. **`SECRET_KEY`** ships with an insecure default for local dev — **must** be overridden in production (`.env`). Enforced by documentation + `.env.example`.

## How to re-verify
```bash
# Backend: import + tests
cd backend && source .venv/bin/activate && python -c "from app.main import app" && pytest
# Frontend: typecheck, build, audit
cd frontend && npx tsc --noEmit && npm run build && npm audit --omit=dev
# Leak scan
grep -rniE "console\.(log|debug)\(.*(key|secret|token)|api_key\s*=\s*[\"']sk-" frontend backend || echo "clean"
```
