# AllHaven — Mobile + AI overhaul (bug fixes & UX), 2026-06-23

Branch `mobile` · 5 commits (`f306405 → 8a0aa36`) · backend suite **530 passing** · mobile + desktop builds green · APK rebuilt to `mobile-latest`.

This addresses every issue reported: mobile approvals, cross-device double records, AI reply quality, AI memory delete-sync, AI knowledge, System Control, mobile settings loading, and moving the connection/Tailscale mode to the top bar.

---

## How I worked
1. **Understand** — 8 parallel deep-readers mapped each subsystem to root causes + fix plans (cited file:line).
2. **Implement** — backend first (testable), then the mobile/desktop frontend.
3. **Verify** — full backend test suite after every change, `tsc` + mobile & desktop Next.js builds, then an **adversarial review** of the two riskiest fixes (which found one real bug, now fixed).

---

## Fixes

### 1. AI replies were "kacau" / only said "completed"  ✅ `f306405`
- **Root cause:** three persistence sites stored `content if status=='completed' and content else (error or status)` — an empty model reply fell through to the literal status word, which the UI rendered as the answer. The persona was also triple-stacked for maximum terseness ("no basa-basi", 1–3 sentences).
- **Fix:** new `ai_reply_text.display_text()` (one place, never returns a status sentinel) used by the orchestrator, multi-agent and reasoning paths. Rewrote the persona (orchestrator `SYSTEM_PROMPT`, context-builder style block, multi-agent + reasoning prompts) to warm, natural, ChatGPT/Claude-style prose; raised the default sampling temperature (kept thinking/deep low for grounded work). Empty single-agent replies now fall back to a friendly sentence.
- **Bonus:** a genuine question that merely mentions money/schedule ("worth ga beli laptop 15 juta?") is no longer hijacked into a canned draft — added `is_question()` and gated finance/schedule auto-routing on it.
- **Frontend guard:** a leftover `completed`/empty bubble renders a muted placeholder instead of the raw word.
- **Tests:** `test_ai_reply_quality.py` (8).

### 2. Mobile approvals unresponsive / errored; couldn't approve & reject  ✅ `7cee757`, `8a0aa36`
- **Root causes:** supabase-js calls had **no timeout** (a slow link froze the button forever); reject used `.single()` → a benign already-handled row threw a scary "not found"; desktop-only tools flipped the card to NEEDS_EDIT and looped on every tap; the 12 s poll replaced the whole list and **resurrected** a card you just resolved; the approvals page used one shared `busyId` that disabled every card + the modal.
- **Fix:** every mutation now races an 18 s timeout (→ clean "connection slow, try again", button returns to idle); reject is tolerant (already-handled = success); desktop-only tools are detected **before** claiming (stay PENDING for desktop) and show a one-line "approve on desktop" note with the Approve button disabled; pollers exclude locally-resolved ids so resolved cards don't flicker back; per-card busy state.

### 3. Desktop + mobile both accepted → duplicate ("double") records  ✅ `7cee757`, `8a0aa36`
- **Root cause:** desktop (Postgres) and mobile (Supabase) are two DBs; each claimed and executed independently before `executed_at` synced. The only hard backstop — the `dedup_key` UNIQUE index (migration 0019) — **is not applied on Supabase** (I probed it live).
- **Fix (code):** the mobile approve claim now adds an `executed_at IS NULL` guard mirroring desktop (closes the common sequential race once `executed_at` syncs); a `dedup_key` unique violation (`23505`) is treated as **already-applied success** (card clears, no error loop) instead of a raw 400.
- **⚠️ Action required from you (closes the rare simultaneous race fully):** apply migrations **0019 + 0020** to Supabase — see *Action items* below. Until then mobile stays tolerant (no crash), but a same-second double-approve on both devices can still produce a duplicate.
- **Adversarial-review fix (`8a0aa36`):** a timeout *after* the claim no longer strands a proposal in `APPROVED` (which was invisible on mobile + un-approvable on desktop) — it resets to PENDING with a "verify in Finance/Calendar first" note.

### 4. Deleting a memory on desktop → it reappears after refresh  ✅ `c5f4841`, `7cee757`
- **Root cause:** `delete_memory` was a **hard** delete; the two-way sync has no delete-propagation, so the next pull re-inserted the still-present Supabase row.
- **Fix:** `ai_memories` gains `is_deleted` + `deleted_at` (migration 0020); delete/clear are now soft-deletes (an UPDATE that LWW sync carries, and whose newer `updated_at` beats the stale remote row, so the desktop deletion **stays deleted** even before Supabase is migrated). Every read filters it. A **re-learn guard** stops background extraction from re-creating or re-suggesting a memory you deleted (only a manual re-add revives it). Mobile memory list/search/create/update/delete/enable/disable/clearAll now run Supabase-direct (they used to hit the unreachable desktop backend).
- **Tests:** `test_memory_soft_delete.py` (3).
- **⚠️ Action required for cross-device convergence:** apply migration 0020 to Supabase (below). Desktop durability already holds without it.

### 5. AI knowledge should be real, not fake  ✅ `3047edf`
- **Finding:** knowledge **is** genuinely injected into the model prompt (verified the path) — not decorative. But it fired on **every** message and dumped the document inventory into every casual chat, and a single shared stop-word could inject an irrelevant chunk, which made it feel random/fake.
- **Fix:** a relevance min-score gate (weak matches dropped), `_wants_knowledge` no longer triggers on trivial greetings, and the inventory is only advertised when knowledge is actually relevant.
- **Tests:** `test_ai_knowledge_gating.py` (3).

### 6. Settings Start/Stop/Restart were "fake"  ✅ `c5f4841`, `7cee757`
- **Finding:** they were **not** fake — they proxy to a privileged localhost agent (:8765); the agent simply **wasn't running** because a bare `uvicorn`/`restart backend` never launched it. (I started it — System Control works on desktop now.)
- **Fix:** `allhaven.sh restart backend` now also ensures the agent; a new local-only `POST /system/agent/start` + a "Start control agent" button turn the old dead-end banner into one-click recovery. On mobile the page honestly says System Control is desktop-only (it manages processes on your computer; a phone can't).

### 7. Mobile settings loaded forever; AI tools unusable without Tailscale  ✅ `7cee757`
- **Root cause:** AI Tools / AI Chat / System Control self-fetched from the REST desktop backend with no fast unreachable-state, so they spun for the full timeout.
- **Fix:** each renders `SetupRequiredState` instantly when the backend is unreachable, **short-circuits on mobile** without firing the doomed request, and System Control no longer polls a dead backend. (These sections are genuinely backend-only — secrets/registry live server-side — so on mobile they show an honest "connect a backend" state rather than a fake panel; with the Tailscale bridge connected they load real data.)

### 8. Move the Tailscale/connection mode to the top menu  ✅ `7cee757`
- **Fix:** a new **top-bar Connection switcher** (Auto / Localhost / Tailscale) with a live status dot, backed by `lib/connectionMode.ts`, broadcasting a change event so the UI repoints instantly — the mode is chosen from the top bar, not buried in AI/Settings config.

### 9. UI/UX polish  ✅
Honest loading/empty/error states across settings, the approvals flow, and the new switcher; clearer desktop-only / needs-backend messaging.

---

## ⚠️ Action items for you (Supabase — needs your DB credentials)
The local desktop DB is fully migrated. Two migrations must also be applied to **Supabase** to fully close the cross-device duplicate race (0019) and make memory deletes converge to the phone (0020). I can't do this — there's no Supabase Postgres password in the env, and it's your production DB.

**Easiest:** Supabase → SQL Editor → paste & run `backend/alembic/supabase_manual_0019_0020.sql` (idempotent, additive, safe on existing rows).
**Or:** `cd backend && ALLHAVEN_DB_TARGET=supabase DATABASE_URL='postgresql+psycopg://postgres.<ref>:<password>@<host>:5432/postgres' .venv/bin/alembic upgrade head`

All shipped code is tolerant of these columns being absent, so nothing breaks before you apply them.

---

## Verification
- Backend: **530 tests pass** (added 14: reply-quality, memory soft-delete, knowledge gating).
- Frontend: `tsc --noEmit` clean; **mobile and desktop `next build` both succeed**.
- Adversarial review of the idempotency + memory-sync diffs: memory fix confirmed correct; one approval-timeout edge found and fixed (`8a0aa36`).
- Live: backend `/health` 200, control agent `/ping` ok, desktop web serving on :3000, backend reachable over Tailscale, APK rebuilt to `mobile-latest`.

## Not done / deliberately out of scope
- **Semantic (embedding) knowledge retrieval** — large infra change (pgvector on Supabase + a backfill + append-only-chunk sync changes). Current retrieval is lexical but now properly gated; flagged as a future enhancement.
- **Knowledge on mobile** depends on the desktop dual-auth bridge (mobile has no backend); unchanged here.
- Applying 0019/0020 to Supabase (your credentials — see above).
