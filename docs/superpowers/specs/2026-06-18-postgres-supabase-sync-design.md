# Design — Two-way Postgres ⇄ Supabase sync + mobile-on-Supabase

- **Date:** 2026-06-18
- **Target release:** v3.7 (foundation + data features); compute features follow in v3.8/v3.9
- **Status:** Approved design, pending implementation plan
- **Related:** `backend/app/services/supabase_sync_service.py` (existing one-way mirror), `docs/DEPLOYMENT.md` (Supabase as managed Postgres), 3.6 mobile bearer login.

## 1. Goal

Make AllHaven usable across desktop and mobile with a single shared dataset:

- **Desktop stays local-first.** Native PostgreSQL remains the desktop's primary database — chosen for **offline capability** and **speed**. The FastAPI backend keeps reading/writing it.
- **Supabase is the shared cloud convergence database**, kept **two-way in sync** with the desktop's local Postgres so both are always identical and up to date.
- **Mobile talks ONLY to Supabase** — no AllHaven backend in the mobile path. Mobile uses Supabase Auth + Row Level Security (RLS) + (later) Realtime/Edge Functions. This works even when the desktop machine is off.

The end-state goal is "every feature works on mobile, via Supabase." Delivery is **phased** (user decision):

- **v3.7** — foundation + all *data* features: Supabase schema, RLS, auth provisioning, two-way sync engine, and mobile-direct-Supabase for the CRUD feature set.
- **v3.8/v3.9** — server-only features (AI agents, third-party integrations with secrets, automation execution, Drive files, knowledge/RAG) ported to **Supabase Edge Functions + Vault + Storage**.

## 2. Non-goals (for v3.7)

- Running AI/LLM orchestration, third-party integration calls, or automation execution from the mobile client. These require server-side compute and secrets that must never ship in an APK; they move to Edge Functions in a later release.
- Multi-user collaboration / sharing. The product is effectively single-user per workspace today; the design must not break when sharing is added, but sharing is not built here.
- A general conflict-resolution framework (CRDT/operational transform). v3.7 uses Last-Write-Wins, which is sufficient for a single user across a few devices.

## 3. Background — current state (grounded in code)

These facts shape the design and are why most of it is low-risk:

- **Client-generatable UUID PKs everywhere.** Every model mixes in `UUIDPrimaryKeyMixin` with `default=uuid.uuid4` (Python-side, not a DB default) via a portable `GUID` type (`backend/app/domain/base.py:29-92`). Desktop, mobile, and Supabase can each mint IDs offline with no collisions and no remapping.
- **`updated_at` exists on ~22 tables** via `TimestampMixin` (`base.py:95-106`) as `TIMESTAMPTZ`. This is the natural LWW clock and incremental watermark. **Caveat:** `updated_at` uses ORM-side `onupdate=func.now()` only — there is **no DB trigger**, so a write that bypasses the SQLAlchemy ORM (raw SQL, a Supabase/PostgREST write, the current upsert) does **not** bump it. This is the single biggest correctness gap for two-way sync.
- **Soft-delete via `is_deleted` boolean** on the core product tables (tasks, task_checklist_items, notes, finance_categories, transactions, calendar_events, drive_files, automations, integration_configs, ai_agent_configs). There is **no `deleted_at`** column anywhere. Append-only / chat / AI / user / session / weather tables are hard-deleted.
- **Identity is one UUID per user:** `LocalUser.id == Profile.id == Workspace.owner_id == WorkspaceMember.user_id` (`auth_service.py:33-72`). `Profile.id` *is* the user id (1:1, by equal PK, no FK). Membership lives in `workspace_members(user_id, workspace_id, role)`.
- **Auth today** is a local MVP: PBKDF2-HMAC-SHA256 password hashes (NOT bcrypt; `security.py:29-56`), a hand-rolled HS256 bearer JWT (`sub = str(user.id)`), and opaque DB-backed browser cookie sessions with CSRF. Every service already scopes by `principal.workspace_id` — the application-layer equivalent of the RLS policy we need.
- **Alembic migrations are portable to Supabase as-is.** 9 migrations, 29 `CREATE TABLE`, linear chain, **no extensions, no enums, no raw SQL, no pgvector** (AI knowledge stores `Text` + `JSONB`, not embeddings). `env.py` reads `settings.DATABASE_URL`. Pointing `DATABASE_URL` at Supabase and running `alembic upgrade head` builds the identical schema.
- **Existing sync is the seed:** `supabase_sync_service.py` does one-way, full-table, fire-after-every-write REST upserts (`Prefer: resolution=merge-duplicates`), errors swallowed to `log.debug`. `local_first_sync.py` is a 23-line wrapper with no pull/watermark logic. We extend this rather than greenfield.
- **Frontend has a single data seam:** `frontend/lib/api.ts` is the only file that calls `fetch()`; every page/component imports the 15 `*Api` objects (~124 methods). Build target is switched today by `BUILD_TARGET=mobile` + `NEXT_PUBLIC_AUTH_MODE=bearer` (`build:mobile`), with `BEARER_MODE` read as a module const and `@capacitor/preferences` lazily imported so it never enters the web bundle.

## 4. Architecture overview

```
        DESKTOP (local-first)                          CLOUD
 ┌────────────────────────────────────┐      ┌────────────────────────────┐
 │ Next.js → FastAPI → Postgres (local)│      │          SUPABASE          │
 │           (desktop source of truth, │      │   Postgres + Auth + RLS    │
 │            offline + fast)          │ 2-way│        + Realtime          │
 │                    │                │◄────►│   (shared convergence DB)  │
 │            Sync engine (NEW)        │ push │                            │
 └────────────────────────────────────┘  +pull└───────────┬────────────────┘
                              LWW by updated_at            │ supabase-js
                                                           │ Auth + RLS (direct,
                                                           │ no AllHaven backend)
                                                  ┌────────┴─────────┐
                                                  │   MOBILE (APK)   │
                                                  └──────────────────┘
```

Desktop writes to local Postgres. A new **sync engine** in the backend keeps local Postgres ⇄ Supabase converged incrementally in both directions. Mobile reads/writes Supabase directly under RLS, independent of whether the desktop machine is online.

## 5. Component A — Supabase schema, RLS, and triggers

1. **Stand up the schema for free.** Set `DATABASE_URL` to the Supabase Postgres connection string and run `alembic upgrade head`. Use the **direct connection (5432)** or **session pooler** for migrations, not the transaction pooler (6543) — and keep the `postgresql+psycopg://` (psycopg v3) driver. Local Postgres keeps its own separate `DATABASE_URL`.

2. **RLS as a new, Supabase-only Alembic migration** (e.g. `0010_supabase_rls`), guarded so the local-Postgres pipeline can stop before it (label/env guard — local Postgres has no `auth.uid()`). Policies:
   - **Workspace-scoped tables** (tasks, notes, finance_*, calendar_events, drive_files, automations, weather_locations, integration_configs, ai_agent_configs, chat_*, ai_*): `USING (workspace_id IN (SELECT workspace_id FROM workspace_members WHERE user_id = app_user_id()))`, `TO authenticated`, with a matching `WITH CHECK` on writes.
   - **User-scoped tables:** `profiles` → `id = app_user_id()`; `workspaces` → `owner_id = app_user_id()`; `workspace_members` → `user_id = app_user_id()`.
   - **`audit_logs.workspace_id` is nullable** → its policy must handle NULL (restrict NULL rows to owner/admin only).
   - Avoid **recursive RLS** on `workspace_members` by reading membership through a `SECURITY DEFINER` helper, and resolve identity through one helper `app_user_id()` (see Component B). Both helpers live in a non-exposed schema and check `auth.uid()` internally.
   - Combine `TO authenticated` **with** the ownership predicate (role check alone is BOLA/IDOR). UPDATE policies get both `USING` and `WITH CHECK`.

3. **Authoritative `updated_at` trigger.** Add a `BEFORE INSERT OR UPDATE` trigger (Supabase `moddatetime`-style) on every synced table **on both databases** so `updated_at` is set by the DB regardless of write path. The sync-apply path is the one exception: when it writes a row pulled from the peer, it must **preserve the peer's `updated_at`** (apply with the trigger suppressed / value forced) so LWW timestamps stay comparable and the row does not look "newer" and echo back.

4. **Key handling.** Only the **backend** holds the `service_role` key (for sync + admin provisioning); it bypasses RLS. The **mobile app only ever holds the anon/publishable key + the user's Supabase JWT** — `service_role` is never bundled into the APK.

## 6. Component B — Identity & Supabase Auth provisioning

The whole RLS model needs `auth.uid()` (Supabase) to resolve to the app's user UUID. Define one helper:

```
app_user_id() RETURNS uuid   -- SECURITY DEFINER, returns the app user id for the current Supabase session
```

Identity mapping — **resolved during planning (2026-06-18):** GoTrue's admin endpoint `POST /auth/v1/admin/users` does **not** accept a caller-supplied `id`; Supabase mints the auth user's UUID server-side and returns it. The same-UUID idea is therefore **not implementable**, so we use the **mapping-column** approach:

- Add `supabase_user_id UUID` (nullable, unique) to `profiles`. On provisioning, create the Supabase Auth user, read the returned `id` from the response, and store it on the user's profile.
- `app_user_id()` (`SECURITY DEFINER`, `STABLE`) maps the current `auth.uid()` → the app user id via `SELECT id FROM profiles WHERE supabase_user_id = auth.uid()`. **Every RLS predicate uses `app_user_id()`**, never `auth.uid()` directly, so the indirection is centralized in one helper.

Provisioning flow:

1. **New signups:** `register_user` has the plaintext password in hand, so after creating the local user/profile/workspace/member it also creates the matching Supabase Auth user (email + password) via the backend using `service_role`.
2. **Existing users (no copyable hash — PBKDF2 ≠ bcrypt):** a **"Connect to Supabase"** action in Settings asks for the current password once, then provisions the Supabase Auth user. (Alternatives considered: rehash-on-next-login, or forced reset email — the explicit button is simplest for a single-user MVP.)

   **Credential source for provisioning:** `register_user` runs before any authenticated/workspace context exists, and a brand-new workspace has no `IntegrationConfig` row yet — so **signup-time** provisioning can only use the **env-level `settings.SUPABASE_URL` + `settings.SUPABASE_SERVICE_ROLE_KEY`** (set by the self-hosted operator). The **"Connect to Supabase"** path is authenticated and reads per-workspace `IntegrationConfig` (service_role_key, decrypted) with the same env-level fallback. Both use a dedicated service-role resolver — distinct from `supabase_sync_service._get_credentials`, which returns the **anon** key and must not be used for admin calls.
3. **Mobile login** uses Supabase Auth directly (email + password) → Supabase JWT → `supabase-js` queries are RLS-scoped. This **supersedes the 3.6 bearer-token login for mobile**; web/desktop keep their existing cookie/bearer auth.

Constraint: provisioning must keep `workspace`/`workspace_members` rows in lockstep with the auth user — `_principal_for_user` requires a default workspace, so an auth user with no workspace row would break.

## 7. Component C — Two-way sync engine (backend)

Replaces the current one-way, full-table, per-write mirror with an incremental two-way engine.

1. **`sync_state` table (new migration):** `(workspace_id, table_name, direction, last_updated_at, last_pk)` — the per-table, per-direction watermark/cursor. This is a prerequisite; nothing like it exists today.
2. **Push (local → Supabase):** `SELECT * WHERE updated_at > last_updated_at ORDER BY updated_at, id` → upsert by PK with `Prefer: resolution=merge-duplicates`, **sending `updated_at` explicitly**. Advance the watermark.
3. **Pull (Supabase → local):** `GET /rest/v1/{table}?select=*&updated_at=gt.{watermark}&order=updated_at.asc` → inverse deserializer (the mirror of the existing `_serialize`, parsing UUID/TIMESTAMPTZ/JSONB back) → **LWW merge by PK**: write the incoming row only if its `updated_at` is newer than the local row's (or the row is absent locally).
4. **Conflict resolution = Last-Write-Wins by `updated_at`.** Acceptable because the product is effectively single-user; true concurrent edits to the same row are rare. Deletes follow "delete-wins-if-newer".
5. **Deletes / tombstones:** soft-delete already propagates as an ordinary row update for the core tables (`is_deleted=true` is just an UPDATE that the watermark pull/push carries). Add a **`deleted_at TIMESTAMPTZ`** alongside `is_deleted` so a delete can be LWW-ordered against a concurrent edit. Hard-delete-only tables (chat/AI/memory/knowledge) are append-mostly; for v3.7 they sync inserts/updates but delete-propagation for them is deferred (documented limitation), or gets soft-delete added when those features land on mobile.
6. **Anti-loop / echo suppression:** when the engine applies a pulled row, it must **not** re-trigger a push (origin suppression), and unchanged rows (equal `updated_at`) are skipped. The current "spawn a daemon thread that re-uploads all ~26 tables on every write" model is replaced by **one debounced background worker per workspace** that runs incremental push+pull. The synced model list should be derived from a registry/mapper, not hardcoded, to avoid silent omissions.
7. **`updated_at`-less append-only tables** (`audit_logs`, `chat_messages`, `ai_tool_calls`, `ai_agent_responses`, `ai_knowledge_chunks`, `ai_memory_suggestions`, `ai_tool_proposals`) watermark on `created_at` instead. Two of them mutate status without a timestamp bump (`ai_tool_proposals`, `ai_memory_suggestions`) — they need an `updated_at` if their status changes must sync; deferred with the AI feature set.
8. **Realtime (progressive):** the worker polls every few seconds while active; an optional enhancement is a **Supabase Realtime** subscription on the desktop so mobile writes land near-instantly.
9. **Errors must surface.** Today every sync failure is swallowed to `log.debug`. The engine needs visible status + a retry path (the existing `routinesApi.syncStatus` / Settings surface is the place to show it) so the two databases can't silently diverge.

## 8. Component D — Mobile data layer (frontend)

1. **One new implementation behind the same seam.** Add `frontend/lib/apiSupabase.ts` exposing the **identical `*Api` interface** but backed by `supabase-js`. `frontend/lib/api.ts` re-exports the REST impl or the Supabase impl based on a new module const `DATA_MODE = process.env.NEXT_PUBLIC_DATA_MODE === 'supabase'`. **Pages and components change nothing** — same pattern as `BEARER_MODE`.
2. **Keep the contract:** the Supabase impl returns the same unwrapped entity shapes (from `@/types`) and throws **`ApiException`-compatible** errors with `statusCode`, so existing branches (e.g. `routinesApi` 404 fallback, `handleUnauthorized`) keep working. Map PostgREST/RLS errors (401/403/`PGRST*`) into `ApiException`.
3. **Bundle hygiene:** lazy `import()` `@supabase/supabase-js` (like the `@capacitor/preferences` precedent) so it never enters the web/desktop bundle. Add `@supabase/supabase-js` to `package.json` (pinned, lockfile committed — supply-chain hygiene).
4. **Build wiring:** add `NEXT_PUBLIC_DATA_MODE=supabase` + `NEXT_PUBLIC_SUPABASE_URL` + `NEXT_PUBLIC_SUPABASE_ANON_KEY` to the `build:mobile` script and `.github/workflows/android-apk.yml` (baked at build time, exactly like the current `NEXT_PUBLIC_API_BASE_URL`). Mobile no longer needs `NEXT_PUBLIC_API_BASE_URL`.
5. **Auth on mobile:** the login screen uses Supabase Auth; the issued Supabase session feeds `supabase-js` so RLS sees the user. Session hydration must run before the first query (mirror of today's `ensureBearerHydrated()` ordering).
6. **v3.7 scope of the port (~35 of ~124 methods):** the CRUD groups that map straight to RLS-protected tables — `authApi`, `tasksApi`, `notesApi`, `financeApi`, `calendarApi`, `weatherApi`, `automationsApi`, plus dashboard reads. The compute/RPC/file groups (`aiApi` 30 methods, `memoryApi` RPC, `knowledgeApi`, `driveApi` multipart, `systemApi`, `n8nApi`, `googleApi`) have no direct-table equivalent — on mobile 3.7 they are read-only or hidden, and move to Edge Functions/Storage in 3.8/3.9.

## 9. Component E — Release scoping

- **v3.7:** Supabase schema + RLS + `updated_at` triggers; Supabase Auth provisioning + "Connect to Supabase"; two-way incremental sync engine (LWW + tombstones + anti-loop + visible status); mobile-direct-Supabase for **Tasks, Notes, Finance, Calendar, Automations, Weather, Dashboard** (plus read access to other data).
- **v3.8/v3.9:** AI agents/multi-agent, third-party integrations (secrets in **Supabase Vault**), automation execution, Drive → **Supabase Storage**, knowledge/RAG — all via **Edge Functions**. The "everything on mobile" goal is reached here.

## 10. Data-model changes required

- New `deleted_at TIMESTAMPTZ` next to `is_deleted` on the soft-delete tables (LWW-orderable deletes).
- New `sync_state` table (watermark/cursor).
- Identity mapping: either same-UUID provisioning or a `supabase_user_id` column on `profiles`.
- Supabase-only migration: `ENABLE ROW LEVEL SECURITY` + policies + `app_user_id()`/`is_member()` helpers + `updated_at`/`moddatetime` triggers.
- (Deferred) `updated_at` on the two status-mutating append-only tables, when their features reach mobile.

## 11. Security checklist (Supabase)

- RLS enabled on **every** exposed table; policies combine `TO authenticated` with an ownership predicate (never role-only).
- UPDATE policies include both `USING` and `WITH CHECK`; no policy lets a row change `workspace_id`/`owner_id` to another tenant.
- `SECURITY DEFINER` helpers (`app_user_id`, `is_member`) live in a non-exposed schema, take no spoofable input, and check `auth.uid()` internally.
- Authorization never reads `user_metadata` (user-editable). Workspace membership is a real table.
- `service_role` key only server-side (backend sync/provisioning). Mobile uses anon/publishable + user JWT. No `NEXT_PUBLIC_*` secret beyond the anon key.
- Any future views use `security_invoker = true`. Future Storage (Drive) buckets get INSERT+SELECT+UPDATE policies for upsert.
- Pin `@supabase/supabase-js`, commit the lockfile.

## 12. Testing & rollout

- **Sync unit tests** (extend `backend/tests/test_supabase_sync.py`): LWW merge (remote-newer wins / local-newer survives), soft-delete propagation, anti-loop (applying a remote row does not enqueue a push), watermark advances correctly and is resumable, append-only tables watermark on `created_at`.
- **RLS tests:** user A cannot read/write user B's workspace; `workspace_members` policy is non-recursive.
- **Provisioning tests:** new signup creates a matching Supabase Auth user; "Connect to Supabase" links an existing user; principal/workspace stays in lockstep.
- **Rollout is opt-in & safe:** sync is enabled via Settings → Integrations (as today). Local Postgres stays the desktop source of truth, so if Supabase is unreachable the desktop keeps working; sync resumes from its watermark.

## 13. Risks & mitigations

| Risk | Mitigation |
|---|---|
| `updated_at` not DB-authoritative (ORM-only) → LWW compares stale timestamps | Add `BEFORE UPDATE` trigger on both DBs; sync-apply preserves the peer timestamp |
| Sync loop / echo once pull lands | Origin suppression + skip equal-`updated_at` rows + single debounced worker |
| Hard-delete tables can't propagate deletes via watermark | Core tables already soft-delete; add `deleted_at`; defer delete-propagation for append-only/AI tables |
| Existing users' PBKDF2 hashes can't migrate to Supabase Auth | "Connect to Supabase" captures password once; never copy hashes |
| Admin API may not allow explicit auth-user id | Fallback `supabase_user_id` mapping + `app_user_id()` helper; verify docs first |
| anon-key sync silently fails once RLS is on | Backend sync uses `service_role`; surface sync errors instead of swallowing |
| Recursive RLS on `workspace_members` | `SECURITY DEFINER` membership helper; non-recursive self-policy |
| Per-write full-table thread doesn't scale | Replace with incremental watermark worker; derive table list from a registry |

## 14. Open items to verify during planning

- ~~Supabase Admin API: can an auth user be created with an explicit id?~~ **Resolved: no — use the `supabase_user_id` mapping column (see §6).**
- Supabase connection mode for Alembic (direct 5432 vs session pooler) and psycopg v3 compatibility — confirm at first migration run.
- Whether `is_deleted` should be added to any v3.7-synced table that currently hard-deletes (deferred with the AI/chat feature set).
- GoTrue admin body: confirm `email_confirm: true` is the correct field to make the provisioned user immediately usable without an email round-trip.
