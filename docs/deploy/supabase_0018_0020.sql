-- Apply pending migrations 0018 + 0019 + 0020 on Supabase.
-- Paste into the Supabase dashboard SQL Editor and run once.
--
-- Equivalent to `ALLHAVEN_DB_TARGET=supabase DATABASE_URL=<supabase-url> alembic upgrade head`
-- from backend/ — use that instead if you have the direct Postgres connection string.
-- Idempotent: safe to re-run.

-- 0018_proposal_idempotency — who executed a proposal + what it produced,
-- so a second approve after cross-device sync 409s instead of duplicating.
ALTER TABLE ai_tool_proposals ADD COLUMN IF NOT EXISTS executed_by uuid;
ALTER TABLE ai_tool_proposals ADD COLUMN IF NOT EXISTS target_entity_id uuid;

-- 0019_proposal_dedup_key — proposal-scoped dedup key on produced rows;
-- unique with NULLs distinct, so existing/manual rows are unaffected.
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS dedup_key varchar(80);
CREATE UNIQUE INDEX IF NOT EXISTS uq_transactions_dedup_key ON transactions (dedup_key);
ALTER TABLE calendar_events ADD COLUMN IF NOT EXISTS dedup_key varchar(80);
CREATE UNIQUE INDEX IF NOT EXISTS uq_calendar_events_dedup_key ON calendar_events (dedup_key);

-- 0020_ai_memory_soft_delete — soft-delete markers; default dropped after
-- backfill to mirror the alembic migration exactly.
ALTER TABLE ai_memories ADD COLUMN IF NOT EXISTS is_deleted boolean NOT NULL DEFAULT false;
ALTER TABLE ai_memories ALTER COLUMN is_deleted DROP DEFAULT;
ALTER TABLE ai_memories ADD COLUMN IF NOT EXISTS deleted_at timestamptz;

-- Record the new head so future `alembic upgrade` runs start from 0020.
UPDATE alembic_version SET version_num = '0020_ai_memory_soft_delete';
