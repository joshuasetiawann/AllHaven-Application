-- ───────────────────────────────────────────────────────────────────────────
-- AllHaven · Supabase manual migration for 0019 + 0020
--
-- WHY: the two-way sync engine and the mobile (Supabase-direct) app rely on a few
-- columns/indexes that exist on the local desktop Postgres but were never applied to
-- Supabase. Probing the live project shows:
--   • ai_tool_proposals.executed_at  → ALREADY present (migration 0018 applied) ✓
--   • transactions.dedup_key         → MISSING (migration 0019)  ✗
--   • calendar_events.dedup_key      → MISSING (migration 0019)  ✗
--   • ai_memories.is_deleted/at      → MISSING (migration 0020)  ✗
--
-- Without 0019's UNIQUE dedup_key index, a proposal approved on BOTH desktop and
-- mobile in the same sync window can insert the SAME finance/calendar row twice (the
-- "double record" bug). Without 0020, a memory deleted on one device reappears after
-- sync. This script adds exactly those columns/indexes. It is IDEMPOTENT (IF NOT
-- EXISTS) and additive — safe to run on a live database with existing rows (the
-- UNIQUE index treats NULL dedup_key as distinct, so legacy/manual rows are untouched).
--
-- HOW TO APPLY (pick one):
--   A) Preferred — run the real Alembic migration so version tracking stays correct:
--        cd backend
--        ALLHAVEN_DB_TARGET=supabase \
--        DATABASE_URL='postgresql+psycopg://postgres.<ref>:<db-password>@<host>:5432/postgres' \
--        .venv/bin/alembic upgrade head
--      (Get the connection string from Supabase → Project Settings → Database.)
--   B) Or paste this whole file into Supabase → SQL Editor → Run, then (optionally)
--      keep Alembic in sync:  UPDATE alembic_version SET version_num='0020_ai_memory_soft_delete';
-- ───────────────────────────────────────────────────────────────────────────

-- 0019 · proposal-scoped dedup_key on the two tables proposals can write to.
ALTER TABLE public.transactions    ADD COLUMN IF NOT EXISTS dedup_key varchar(80);
CREATE UNIQUE INDEX IF NOT EXISTS uq_transactions_dedup_key    ON public.transactions    (dedup_key);

ALTER TABLE public.calendar_events ADD COLUMN IF NOT EXISTS dedup_key varchar(80);
CREATE UNIQUE INDEX IF NOT EXISTS uq_calendar_events_dedup_key ON public.calendar_events (dedup_key);

-- 0020 · durable, sync-safe soft-delete for AI memories.
ALTER TABLE public.ai_memories ADD COLUMN IF NOT EXISTS is_deleted boolean NOT NULL DEFAULT false;
ALTER TABLE public.ai_memories ADD COLUMN IF NOT EXISTS deleted_at timestamptz;
CREATE INDEX IF NOT EXISTS ix_ai_memories_is_deleted ON public.ai_memories (is_deleted);
