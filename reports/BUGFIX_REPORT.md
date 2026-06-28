# AllHaven — Bugfix Report

- **App version:** v3.8.0
- **Date:** 2026-06-19
- **Branch:** `main`
- **Standing rules honored:** no faked success (every fix has a concrete verification), no user-data deletion, no secrets hardcoded/exposed, root causes over symptoms.

This report covers the four observed bugs from the stability-repair pass. Two were already fixed earlier this cycle; one was re-diagnosed (the symptom and the root cause differed); one was a build-hygiene issue.

---

## Bug 1 — Desktop renders as plain HTML (no CSS)

- **Severity:** High (app looks broken on desktop dev).
- **Symptom:** The desktop app occasionally loads unstyled — plain HTML, no Tailwind.
- **Root cause:** A stale/partial `.next` dev cache. Running production/verification builds against the same `.next` directory that the running `next dev` server uses leaves the dev server pointing at a CSS asset path that no longer exists → the stylesheet 404s and the page renders unstyled. Not a CSS authoring problem.
- **Fix:** A `predev` npm hook that wipes `.next` before every `next dev`, so each dev session starts from a clean, self-consistent cache:
  ```json
  "predev": "node -e \"require('fs').rmSync('.next',{recursive:true,force:true})\""
  ```
  (`frontend/package.json`)
- **Verification:** Started the dev server via `npm run dev` (which triggers `predev`), then fetched the page and probed its stylesheet:
  - `/login` references `/_next/static/css/app/layout.css`
  - That URL returns **HTTP 200, 70 459 bytes** of compiled Tailwind.
- **Status:** ✅ Fixed.

---

## Bug 2 — Tasks: checklist schema error on create

- **Severity:** High (blocked task creation with a checklist on mobile).
- **Symptom:** Creating a task with checklist items failed with a PostgREST schema-cache error referencing a `checklist` column on `tasks`.
- **Root cause:** The Supabase create path passed the whole payload — including the synthetic `checklist` array — straight into `insert()`. `tasks` has no `checklist` column (checklist items live in the separate `task_checklist_items` table), so PostgREST rejected the insert.
- **Fix:** `frontend/lib/apiSupabase.ts` `tasksApi.create` now destructures `checklist` out of the task fields, inserts the task with defaults, then writes the checklist titles (capped at 5) as `task_checklist_items` rows with client-minted scope:
  ```ts
  const { checklist, ...taskFields } = payload;
  // insert task (status TODO, priority NORMAL, ...newRow()) → get id
  // insert task_checklist_items rows {task_id, title, position, ...newRow()}
  ```
- **Verification:** `next build` clean; backend `pytest` **422 passed**; audit confirms the Supabase query targets `task_checklist_items` (not `tasks.checklist`).
- **Commit:** `1fb97be`.
- **Status:** ✅ Fixed.

---

## Bug 3 — Mobile registration blocked

- **Severity:** High (new users couldn't sign up from the phone).
- **Symptom:** Registration on mobile failed / couldn't establish a usable session.
- **Root cause:** Supabase-direct mobile mode had no provisioning step. A raw Supabase `signUp` does not create the backend `profiles` / `workspaces` rows that RLS (`app_user_id()`, `is_member()`) depends on, so even a created auth user couldn't read or write any data.
- **Fix:** `frontend/lib/apiSupabase.ts` `authApi.register` now provisions through the backend first, then signs in to Supabase:
  ```ts
  register: async (email, password, fullName) => {
    await restAuthApi.register(email, password, fullName); // creates LocalUser + profile + workspace + Supabase account
    return supabaseSignIn(email, password);                // signInWithPassword → loadMe()
  }
  ```
- **Verification:** `next build` clean; audit confirms Auth Register works desktop + mobile (both create profiles/workspaces on the backend, then the phone reads via Supabase RLS).
- **Commit:** `1fb97be`.
- **Status:** ✅ Fixed.
- **Note:** Registration provisioning needs the backend reachable (Tailscale) the first time, by design — it is what creates the RLS-visible profile/workspace.

---

## Bug 4 — "Routine settings not working"

- **Severity:** High (repeat settings appeared to do nothing).
- **Reported symptom:** Configuring a routine to repeat had no effect.
- **Investigation (root cause ≠ symptom):** The settings **do** persist — the deep-dive confirmed `repeat_rule`, `repeat_days`, `time_period`, icon, color, location all save and reload correctly. The real defect was that recurring rules were **never materialized**: a routine rendered only on its anchor date. Navigating to any future day showed nothing, so "repeat daily/weekly" looked broken even though it was saved.
- **Fix (client-side occurrence expansion, no DB row duplication):**
  - `frontend/components/routines/shared.ts`: added `occursOn(routine, dayKey)`, `expandForDay()`, `countOn()`, `isUpcoming()`, `baseOf()`, and the `RoutineOccurrence` type. Expansion preserves time-of-day and event duration, honors the `repeat_days` weekday filter, and for `monthly` correctly skips months that lack the anchor's day-of-month (no phantom Feb-30).
  - `frontend/app/dashboard/routines/page.tsx`: the selected-day view now expands recurrences; the date-strip per-day counts, the **Today** count, and the **Upcoming** count include recurrences; editing or deleting an expanded instance resolves back to the underlying routine via `baseOf()` (so editing a Wednesday instance of a daily routine edits the series, not a phantom).
- **Why client-side:** It fixes already-saved routines immediately with zero migration/backend dependency, and avoids duplicating rows in `calendar_events`.
- **Verification:** `tsc --noEmit` **0 errors**; `next build` clean (all routes, incl. `/dashboard/routines`); dev server compiled `/dashboard/routines` → **HTTP 200**.
- **Commit:** `c50aa32`.
- **Status:** ✅ Fixed.

---

## Out of scope (documented, deferred — see FULL_FEATURE_AUDIT_REPORT.md)

The audit surfaced two genuinely missing *features* (not regressions) behind "routines": **alarm persistence** (no DB columns/UI) and **alarm execution** (no scheduler). These require a migration + a background scheduler and are deferred to the backend phase per the "fix bugs first, then backend" sequencing. They are tracked in the audit report's "Known gaps" with a suggested implementation order.

## Commit trail (this cycle)

| Commit | What |
|--------|------|
| `c50aa32` | Recurring routine expansion (Bug 4). |
| `1fb97be` | Task-checklist create schema fix (Bug 2) + mobile registration (Bug 3). |
| `3f8e274` | Client-side id minting for Supabase inserts (the earlier "id not full constraint" class of write failures). |
| `326d3bf` | Mobile UI declutter (responsive; desktop unchanged). |
| `4bea8d8` | v3.8.0 release (full mobile, unified accounts, weather removal). |

Bug 1 (the `predev` clean) shipped with the v3.8.0 build-hygiene changes.
