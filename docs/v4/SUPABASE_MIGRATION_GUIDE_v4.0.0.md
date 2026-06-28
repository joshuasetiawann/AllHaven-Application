# Supabase Migration Guide — AllHaven v4.0.0

Apply migrations **0016** and **0017** to your hosted Supabase project before relying
on standalone mobile registration and two-way approval/suggestion sync.

> **Never paste real credentials into this doc, a commit, or a chat.** Use a local
> `.env`/shell var for `DATABASE_URL` and the Supabase dashboard for the SQL editor.
> Nothing in this guide requires hardcoding a secret.

---

## 1. What you're applying

| Migration | File | Adds | Reversible |
|---|---|---|---|
| **0016** | `backend/alembic/versions/0016_provision_me.py` (= `docs/deploy/provision_me.sql`) | `public.provision_me(p_full_name text)` — `SECURITY DEFINER` RPC. Creates profile + workspace + owner membership for a brand-new signed-up user. Idempotent; adopts an existing same-email profile (desktop-first accounts) instead of duplicating. | `drop function` |
| **0017** | `backend/alembic/versions/0017_proposal_sync_fields.py` | `ai_tool_proposals.updated_at`, `ai_tool_proposals.error_message`, `ai_memory_suggestions.updated_at`, plus a `BEFORE UPDATE` trigger (`trg_set_updated_at` → `set_updated_at()`) on both tables. Backfills `updated_at = created_at` on existing rows. | `drop_column` / `drop trigger` |

Both are **additive** on local Postgres and on Supabase — no enum or constraint changes.

### Features that depend on each migration

| Feature | Needs |
|---|---|
| **Standalone mobile registration** (register via `provision_me` RPC, no backend reachable) | **0016** |
| **Adopting a desktop-first account on mobile** (same email links instead of duplicating) | **0016** |
| **Approvals (AI tool proposals) converging desktop ↔ mobile** (approve/reject on one device propagates via LWW sync) | **0017** (`updated_at`) |
| **Failed approvals staying visible** (FAILED / NEEDS_EDIT reason persists) | **0017** (`error_message`) |
| **AI Memory suggestions converging desktop ↔ mobile** (accept/reject syncs) | **0017** (`updated_at`) |

> **Without 0016**, mobile register fails with:
> `Could not find the function public.provision_me in the schema cache`.

---

## 2. Pre-flight checklist

- [ ] You have the Supabase project's **direct Postgres connection string** (for the alembic path) or **SQL editor** access (for the SQL path).
- [ ] Migrations 0001–0015 are already applied (Supabase schema provisioned via `alembic upgrade head`). 0016/0017 are additive on top.
- [ ] Apply during a quiet window — 0017 backfills `updated_at` on existing rows.
- [ ] Credentials live only in your shell/`.env`, never in a tracked file.

---

## 3. How to apply

You have two routes. **Alembic applies both 0016 and 0017** and stamps the version
table — prefer it. The **SQL editor route covers 0016 only** (it's the fast hotfix
for the register error); you must still run alembic for 0017.

### Option A — Alembic (recommended; applies 0016 **and** 0017)

From the `backend/` directory, with `DATABASE_URL` pointed at Supabase and the
target flag set:

```bash
cd backend
ALLHAVEN_DB_TARGET=supabase DATABASE_URL="$SUPABASE_DATABASE_URL" alembic upgrade head
```

- `ALLHAVEN_DB_TARGET=supabase` selects the Supabase target.
- `DATABASE_URL` is the Supabase Postgres connection string — keep it in your
  shell env (`export SUPABASE_DATABASE_URL=...`) or `.env`, **not** in this file.
- `upgrade head` walks to the latest revision: `... → 0016_provision_me → 0017_proposal_sync_fields`.

### Option B — Supabase SQL editor (0016 only)

For the register hotfix without running alembic:

1. Supabase Dashboard → **SQL Editor** → New query.
2. Paste the entire contents of **`docs/deploy/provision_me.sql`**.
3. **Run.**

This file is byte-for-byte equivalent to migration 0016. It is `SECURITY DEFINER`,
idempotent (safe to run twice — it `drop function if exists` first), grants
`execute` to `authenticated`, and ends with `notify pgrst, 'reload schema';` so the
RPC is exposed immediately.

> After Option B you still need **0017** for approval/suggestion sync — run Option A
> (alembic), which will skip 0016 if already present and apply 0017.

---

## 4. Schema-cache reload (PostgREST)

PostgREST caches the schema. A newly created function/column won't be reachable over
`/rest/v1/...` until the cache reloads.

- `docs/deploy/provision_me.sql` already ends with:

  ```sql
  notify pgrst, 'reload schema';
  ```

- If you applied via alembic, or the column/RPC still 404s, trigger a reload manually
  in the SQL editor:

  ```sql
  notify pgrst, 'reload schema';
  ```

A successful `NOTIFY` makes the RPC and new columns visible within a moment.

---

## 5. How to verify

### 5.1 `provision_me` RPC is exposed (not 404)

Probe the PostgREST RPC endpoint. A **404** means PostgREST can't see the function
(migration not applied or cache not reloaded). Anything other than 404 (e.g. 401/400
for a missing auth/body) means the function is registered.

```bash
# Replace placeholders with your project ref + anon key (do NOT commit them).
curl -i -X POST \
  "https://<PROJECT_REF>.supabase.co/rest/v1/rpc/provision_me" \
  -H "apikey: $SUPABASE_ANON_KEY" \
  -H "Content-Type: application/json" \
  -d '{}'
```

- **404 `Could not find the function ...`** → not applied / cache stale → re-run §4.
- **Not 404** (200 / 401 / 400) → the RPC exists and is exposed. 

You can also confirm in SQL:

```sql
select proname
from pg_proc
where proname = 'provision_me' and pronamespace = 'public'::regnamespace;
```

### 5.2 New 0017 columns exist

```sql
select table_name, column_name
from information_schema.columns
where (table_name = 'ai_tool_proposals'    and column_name in ('updated_at','error_message'))
   or (table_name = 'ai_memory_suggestions' and column_name = 'updated_at')
order by table_name, column_name;
```

Expect three rows:

| table_name | column_name |
|---|---|
| ai_memory_suggestions | updated_at |
| ai_tool_proposals | error_message |
| ai_tool_proposals | updated_at |

Confirm the trigger too:

```sql
select tgname, tgrelid::regclass as table
from pg_trigger
where tgname = 'trg_set_updated_at'
  and tgrelid::regclass::text in ('ai_tool_proposals','ai_memory_suggestions');
```

Expect `trg_set_updated_at` on both tables.

### 5.3 Verification checklist

- [ ] `/rest/v1/rpc/provision_me` returns **anything but 404**.
- [ ] `ai_tool_proposals.updated_at` and `ai_tool_proposals.error_message` exist.
- [ ] `ai_memory_suggestions.updated_at` exists.
- [ ] `trg_set_updated_at` present on both tables.
- [ ] Mobile register completes without the schema-cache error.

---

## 6. Troubleshooting

### "Could not find the function public.provision_me in the schema cache"

Seen during mobile registration. In order:

1. **Migration not applied** → run §3 (Option A or B).
2. **Cache not reloaded** → run `notify pgrst, 'reload schema';` (§4).
3. **Wrong signature** → the function is `provision_me(p_full_name text default null)`.
   The SQL file `drop function if exists public.provision_me(text)` first, so
   re-running `docs/deploy/provision_me.sql` cleanly recreates it.
4. **Wrong target** → confirm you applied to **Supabase**, not local Postgres
   (`ALLHAVEN_DB_TARGET=supabase` + Supabase `DATABASE_URL`).
5. Re-verify with §5.1.

### New columns/RPC still 404 after applying

Schema cache is stale — re-run the `NOTIFY` from §4, then re-probe (§5).

### Alembic reports "already at head" but a column is missing

The version table was stamped without the DDL landing (e.g. partial run). Inspect with
the SQL queries in §5.2; if a column is genuinely absent, the safest fix is the SQL
editor route for the specific object, then reconcile the alembic version table.

---

## 7. Email confirmation note

The Supabase project currently has **email confirmation ON** (`mailer_autoconfirm = false`).

- **As-is:** new users go register → receive a confirmation email → confirm → then log in.
- **For instant registration:** Supabase Dashboard → **Authentication → Providers → Email** →
  disable "Confirm email" (i.e. enable autoconfirm). Then register signs the user in
  directly and `provision_me` runs immediately.

This is independent of migrations 0016/0017 — but if confirmation is **on** and you
expect instant register, that's the cause, not the RPC.

---

## 8. Reference

- Migration 0016: `backend/alembic/versions/0016_provision_me.py`
- Migration 0017: `backend/alembic/versions/0017_proposal_sync_fields.py`
- SQL hotfix (0016): `docs/deploy/provision_me.sql`
- Trigger helper `set_updated_at()` originates in migration 0012.
