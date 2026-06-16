# AllHaven — Release Checklist

Status of every release-readiness item. Run the commands, tick the boxes.

## Build & tests
- [x] Backend tests pass — `cd backend && pytest tests/` (full suite green)
- [x] Frontend builds — `cd frontend && npm run build` (no type errors)
- [x] DB migrations clean — `cd backend && alembic upgrade head` (verified on PostgreSQL 16, no drift)
- [x] Health check — `scripts/healthcheck.sh`

## App shell & UI
- [x] One consistent shell (sidebar + topbar + content)
- [x] Topbar clean & responsive (no horizontal overflow; mobile/tablet collapse; nav drawer)
- [x] Sidebar modules all clickable (Drive, Calendar, Weather, Automations, AI, Settings) with MVP badges
- [x] Settings grouped by module; every card shows honest status
      (`not_configured / configured / online / error / disabled / unavailable`)

## Persistence (survives refresh)
- [x] Tasks / Notes / Finance create-update-delete persist (PostgreSQL)
- [x] AI chat sessions + multi-agent runs persist
- [x] Calendar events, Drive file metadata, Automations, Weather locations persist

## Settings & .env sync
- [x] Save persists to DB; allowlisted keys mirror to `.env`
- [x] Timestamped backup before write; atomic write; `chmod 600`; unrelated keys preserved
- [x] `env_sync` status returned to the frontend (success / failed / skipped)
- [x] Secret inputs show masked preview only; raw secrets never returned
- [x] Arbitrary keys rejected; `SECRET_KEY` / `DATABASE_URL` intentionally excluded (documented)

## AI providers (honest verification)
- [x] 15 providers: Ollama + GPT + Claude + Gemini + Cursor + DeepSeek + Qwen + Grok + Blackbox + OpenRouter 1..6
- [x] Save → `configured` (never Online); Online only after a real Test Connection
- [x] Invalid/random key → error; network/allowlist block → `unavailable` (not "key rejected")
- [x] Ollama verified via `/api/tags`; no auto model pull
- [x] OpenRouter has Base URL + light default models; verified chat (Gemini 2.5 Flash Lite) live

## Multi-agent
- [x] Up to 10 agents at once; >10 -> HTTP 422
- [x] Each agent answers in its own card; one agent failing doesn't fail the others
- [x] Conversation + each agent result persisted

## Integrations
- [x] Supabase: URL + anon + service-role (secret) save; Test Connection hits `/auth/v1/health`; honest status; service-role never exposed to frontend; mirrors to `.env`
- [x] Drive: upload / list / download / soft-delete; metadata in DB; path traversal blocked
- [x] Calendar: local event CRUD; Google status honest (no fake sync)
- [x] Weather: real fetch when configured, else `setup_required` (never faked)
- [x] Automations: local CRUD MVP; never executed (disabled-safe); n8n status testable

## Security
- [x] Secrets server-side only; masked previews; no secrets in logs/JSON; none in localStorage
- [x] External-AI privacy warning; AI proposes, human approves writes

## Deploy
- [x] `docker-compose.prod.yml` + Dockerfiles + Caddy auto-HTTPS; `docs/DEPLOYMENT.md`

## Known limitations
- External AI requires the host to be reachable from the backend (blocked hosts → honest "unavailable").
- `DATABASE_URL` / `SECRET_KEY` are not web-editable (bootstrap settings; edit `.env` + restart).
- Automations are drafts only — AllHaven never executes them.
- The `.env` mirror is host-global; the database remains the per-workspace source of truth.
