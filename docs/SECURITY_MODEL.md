# Security Model

## Principles

- No destructive action without explicit confirmation.
- No fake success messages; no faked integrations.
- No hardcoded secrets — configuration via `.env` (only `.env.example` is committed).
- Business data is scoped by `workspace_id`; sensitive endpoints require an authenticated user.
- Audit logs are append-only in normal application behavior.
- User content is soft-deleted by default (no hard delete in the normal API).

## Authentication boundary

The MVP uses a **local auth adapter** isolated in `app/services/auth_service.py` and
`app/api/dependencies.py`. This boundary is intentionally thin so it can be replaced by
**Supabase Auth** (or another provider) without touching routers or services.

### Password hashing & JWT (stdlib)

To keep the one-shot local build free of native-build/version conflicts, the MVP implements:

- **Password hashing:** PBKDF2-HMAC-SHA256 (200k rounds, per-user random salt), constant-time
  verification.
- **Tokens:** HS256 JWT (header.payload.signature) signed with `SECRET_KEY`, with `iat`/`exp`.

Both live in `app/core/security.py` and are **documented as replaceable** by bcrypt/argon2 and a
vetted JWT library (or Supabase-issued tokens) in production. `SECRET_KEY` **must** be set to a
strong random value outside local development.

### Login safety

- Invalid login returns a **generic 401** (`INVALID_CREDENTIALS`) that never reveals whether the
  email or the password was wrong.
- `hashed_password` is never serialized in any response.

## Authorization & data scoping

- Every authenticated request resolves to an immutable `Principal` (`user_id`, `workspace_id`).
- The client **cannot** supply `workspace_id`; services derive it from the `Principal`.
- All queries filter by `workspace_id` and `is_deleted = false`.

## Transport & input

- CORS is restricted to configured frontend origins (`BACKEND_CORS_ORIGINS`).
- Local/dev can reach private LAN and Tailscale integration URLs for Ollama/n8n.
  Production/staging blocks server-side requests to localhost, private LAN,
  link-local, and Tailscale 100.64.0.0/10 addresses unless
  `ALLOW_PRIVATE_INTEGRATION_URLS=true` is set explicitly.
- Swagger/OpenAPI docs are exposed by default only in local/dev. Production can
  opt in with `API_DOCS_ENABLED=true`.
- All input is validated by Pydantic schemas; validation errors return the standard envelope.
- Unhandled errors return a generic 500 — **never a raw stack trace**.

## Auditing

`audit_logs` records create/update/delete (and AI proposal decisions) with before/after
snapshots, the acting user, and the workspace. It is treated as append-only.

## Secrets & integration status

The integration status endpoint reports only `configured` / `status` / a human-readable detail.
**No secret value is ever returned.** A placeholder value (empty, `changeme`, `your-...`, etc.)
is treated as *not configured*.

## Known limitations (MVP)

- Tokens are not refreshable/revocable (short-lived access tokens only).
- Auth endpoints have a single-instance in-memory rate limiter; production with
  multiple replicas should also rate-limit at the gateway.
- No account lockout.
- Local auth is for development; use a hardened provider in production.
