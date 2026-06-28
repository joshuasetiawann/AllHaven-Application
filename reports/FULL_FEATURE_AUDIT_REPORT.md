# AllHaven — Full Feature Audit Report

- **App version:** v3.8.0
- **Date:** 2026-06-19
- **Branch:** `main`
- **Scope:** Every user-facing module across **desktop** (Next.js web/desktop, REST + local Postgres, with two-way Supabase sync) and **mobile** (Capacitor APK, Supabase-direct, bearer auth).
- **Method:** Static code audit of the data-layer seam (`frontend/lib/api.ts` → `apiRest.ts` / `apiSupabase.ts`), backend services/routers, and the relevant page/component trees. This is a wiring + persistence audit, not a pixel-level visual QA (see `MOBILE_QA_REPORT.md` for the responsive review).

## How the two runtimes differ (the mental model)

`frontend/lib/api.ts` chooses the implementation per data group:

- **Supabase-backed groups** (work on mobile *and* desktop): `tasksApi`, `notesApi`, `financeApi`, `routinesApi`, `automationsApi`, `authApi`. On mobile these talk **directly to Supabase** (PostgREST + RLS + Supabase Auth bearer). On desktop they go through REST to the local backend, which mirrors to Supabase via the sync engine.
- **Always-REST groups** (desktop-only in practice): `settingsApi`, `aiApi`, `memoryApi`, `knowledgeApi`, `driveApi`, `systemApi`, `n8nApi`, `googleApi`. These require the backend (they hold provider secrets / compute). On mobile they only work if the backend is reachable (Tailscale), and fail fast at a 6 s timeout otherwise.

This split is intentional: secrets (AI provider keys, Drive credentials) are never shipped to the phone.

## Module status matrix

| # | Module | Desktop | Mobile | Notes |
|---|--------|---------|--------|-------|
| 1 | Auth — Login | ✅ works | ✅ works | Desktop: REST session cookie + CSRF. Mobile: REST register/provision → Supabase `signInWithPassword` (bearer). |
| 2 | Auth — Register | ✅ works | ✅ works | Mobile register now provisions the account via backend, then signs in to Supabase. (Fixed this cycle.) |
| 3 | Dashboard | ✅ works | ⚠️ partial | Core data (tasks/notes/finance) is Supabase-backed and fast. The Integrations panel is REST-only on a **non-blocking** path — empty (not broken) if the backend is unreachable. |
| 4 | Tasks | ✅ works | ✅ works | CRUD via REST/Supabase. Create strips the `checklist` field, inserts the task, then writes `task_checklist_items`. (Schema-cache bug fixed this cycle.) |
| 5 | Task Checklist | ✅ works | ✅ works | Reads `task_checklist_items` (not a non-existent `tasks.checklist` column). Position computed client-side to match backend `max(pos)+1`. |
| 6 | Task Complete / Reopen | ✅ works | ✅ works | DONE+`completed_at` / TODO+null. |
| 7 | Notes | ✅ works | ✅ works | Pinned-then-updated ordering, `is_deleted` filter. |
| 8 | Finance | ✅ works | ✅ works | Categories + transactions CRUD; mobile aggregates the summary/report client-side. IDR default, currency normalized uppercase. |
| 9 | Routines | ✅ works | ✅ works | CRUD + all settings persist (`time_period`, `repeat_rule`, `repeat_days`, icon, color, location). **Recurring expansion fixed this cycle** (see below). AI Generate is desktop-only by design. |
| 10 | AI Chat | ✅ works | 🔌 REST-only | Sessions/messages/providers require the backend. On mobile, degrades to a 6 s fast-fail when the backend is unreachable. |
| 11 | Approvals | ✅ works | 🔌 REST-only | Tool proposals + memory suggestions via REST. |
| 12 | Memory Suggestions | ✅ works | 🔌 REST-only | No Supabase mirror; invisible on mobile without the backend. |
| 13 | Knowledge / Image Upload | ✅ works | 🔌 REST-only | Multipart upload to backend; no Supabase mirror. |
| 14 | Drive | ✅ works | 🔌 REST-only | Upload/download/delete via backend; times out on mobile if unreachable. |
| 15 | Automations | ✅ works | ✅ works | CRUD via REST/Supabase. n8n workflow control is REST-only. |
| 16 | Settings | ✅ works | 🔌 REST-only | Integrations / AI providers / Supabase connection. Hidden in mobile UI; REST timeout if reached. |
| 17 | Integrations | ✅ works | 🔌 REST-only | List/get/save/test/enable/disable. Loaded on a non-blocking path on the dashboard. |
| 18 | AI Providers | ✅ works | 🔌 REST-only | Provider config + model slots + policy. |
| 19 | Calendar | ✅ works | ✅ works | Redirects to `/dashboard/routines` (shared `calendar_events`). |
| 20 | Calculator | ✅ works | ✅ works | Pure client-side, no persistence by design. |
| 21 | Clock | ✅ works | ✅ works | Clock/stopwatch/timer/alarm — all in-page (`setInterval`/WebAudio), no persistence by design. |
| 22 | Sync Status (Routines) | ✅ works | ✅ works | Desktop reports `local_first`/`active`; mobile reports `active`. |

Legend: ✅ works · ⚠️ partial (works, with a documented gap) · 🔌 REST-only (needs the backend; desktop-only in practice).

## Routines deep-dive (the "settings not working" report)

The Routines feature has solid persistence; the reported "settings not working" was a **rendering** gap, not a persistence gap.

| Area | Status | Detail |
|------|--------|--------|
| Routine CRUD persistence | ✅ works | `calendar_events` via REST (desktop) / Supabase (mobile), soft-delete via `is_deleted`. |
| Settings/preferences persistence | ✅ works | All 10 fields stored + reloaded (migration `0009_routine_preferences`). |
| Settings form (`RoutineFormModal`) | ✅ works | Captures repeat rule, 7-day toggle, time period, icon, color, location, notes. |
| AI generation status reporting | ✅ works | Honest `ok`/`not_configured`/`blocked`/`error`; never fabricates drafts. |
| AI generation (mobile) | ⛔ by design | Throws `UNAVAILABLE_ON_MOBILE` to protect the backend AI secret. |
| Batch save (AI drafts → DB) | ✅ works | Atomic: validates all items before any insert. |
| **Recurring expansion** | ✅ **fixed this cycle** | Was: rules stored but only rendered on the anchor date. Now: occurrences materialize on every applicable day (see `BUGFIX_REPORT.md`). |
| Time-period slot awareness | ✅ works | `PERIOD_WINDOWS` (morning 5–12 / afternoon 12–17 / evening 17–24). |
| Alarms / reminders — storage | ⛔ not implemented | No `alarm_*` columns, no UI. See "Known gaps". |
| Alarms / reminders — execution | ⛔ not implemented | No background scheduler. See "Known gaps". |

## Known gaps (not regressions — missing features / by-design limits)

These are **deferred backend work**, intentionally out of scope for the "fix the bugs first" pass:

1. **Routine alarms — persistence (HIGH).** `calendar_events` has no `alarm_minutes_before` / `alarm_type` columns and the form has no alarm controls. Needs a migration + ORM/schema fields + UI.
2. **Routine alarms — execution (HIGH).** No scheduler (no APScheduler/Celery), no notification dispatch. Even with alarm columns, nothing would fire. Needs a scheduler booted from the FastAPI lifespan, plus a mobile delivery path (Supabase Realtime push or device-local notifications).
3. **Mobile "requires desktop" messaging (UX, MEDIUM).** REST-only modules (AI Chat, Drive, Knowledge upload, Routine Generate, Memory suggestions) currently look functional on mobile until they silently time out. Add explicit "available on the desktop app" banners/guards.
4. **Memory / Knowledge on mobile (MEDIUM).** No Supabase mirror for `memoryApi` / `knowledgeApi`; these are compute-side only. Mobile parity would require Supabase tables + RLS.

## Suggested implementation order (if/when greenlit)

1. ~~Recurring routine expansion~~ — **done this cycle.**
2. Mobile "requires desktop" guards/banners (cheap UX hardening, no backend).
3. Alarm persistence: migration + ORM/schema + `RoutineFormModal` controls.
4. Alarm execution: APScheduler + `routine_scheduler.py` + lifespan boot + mobile delivery (depends on #3).

## Verification performed this cycle

- `next build` (web/desktop target): **clean** — compiled, linted, type-checked, all 21 routes prerendered.
- `tsc --noEmit`: **0 errors.**
- Dev server (`npm run dev`, which runs the `predev` `.next` clean): `/login` served `layout.css` → **HTTP 200, 70 KB** of compiled Tailwind; `/dashboard/routines` compiled → **HTTP 200**.
- Backend `pytest`: **422 passed** (prior in this cycle, after the task-checklist fix).
