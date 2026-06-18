# AllHaven v4.2.0 - Release Notes

Date: 2026-07-02

AllHaven 4.2.0 pairs a full visual redesign (Aurora Glass) with the completion of the v4.0 AI-brain audit and a security-hardening pass. Nothing behavioral changed in the redesign; everything behavioral changed in how the AI talks to you.

## Changed

- The entire UI is restyled on the **Aurora Glass** design system: shared tokens and primitives in `globals.css`, glass surfaces, and aurora accents across every page and component. Visual-only — routes, APIs, and data are untouched. A design handoff bundle lives in `design_handoff_allhaven_aurora/`.
- Greetings and smalltalk short-circuit to a warm, instant reply instead of running the full AI pipeline.
- Every AI reply passes a quality gate before display, so robotic "completed"-style output no longer reaches the chat.
- **ROUTINE** is a first-class intent in the deterministic router, and Indonesian "dapat 50rb" phrasing is parsed as income.
- Non-finance proposals (schedule, routine, note, task) render a typed, human-readable approval preview instead of raw JSON.
- Knowledge upload workflow is clearer about states and errors.

## Fixed

- Desktop voice input works again.
- AI memory recall and editing are stabilized; the memory soft-delete migration (0020) is restored.
- Mobile login failures surface the real Supabase/configuration error instead of a generic spinner.
- The launcher clears stale host port listeners on start/restart, backend startup checks are repaired, and native (non-Docker) Postgres status is reported correctly.

## Security

- Private-integration URLs are guarded against SSRF.
- API docs are hidden outside local mode.
- The Drive config endpoint requires authentication.
- Private routes are covered by auth regression tests.

## Deployment

- **Supabase migrations 0018–0020 are required** for cross-device approval idempotency (no double-executed approvals) and memory soft-delete sync. Apply `docs/deploy/supabase_0018_0020.sql` in the SQL editor (idempotent) or run `ALLHAVEN_DB_TARGET=supabase DATABASE_URL=<supabase> alembic upgrade head`. Applied and verified on the project Supabase on 2026-07-02 (`alembic_version` = `0020_ai_memory_soft_delete`).
- Restart the backend after updating so the AI-brain changes take effect.

## Verification

- `pytest` (backend, full suite) -> 575 passed
- `npx tsc --noEmit` -> 0 errors
- `npm run build` (web) -> success
- Version consistency (VERSION == backend == package manifests == nav constant) covered by `backend/tests/test_version.py`
