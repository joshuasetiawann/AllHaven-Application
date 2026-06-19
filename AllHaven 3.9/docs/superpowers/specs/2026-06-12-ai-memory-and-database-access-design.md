# AI Memory System & Safe Database Access — Design Spec

**Date:** 2026-06-12
**Status:** Approved
**Parts:** PART 10 (AI database access via safe tools) + PART 11 (automatic memory learning)

---

## Problem

- AI hanya menjawab dari prompt saat itu; tidak tahu data aplikasi user.
- Memory hanya tersimpan di localStorage, manual, dan tidak dipakai di chat baru.
- AI tidak bisa akses calendar, tasks, notes, finance secara real (meski Tool Registry sudah ada).
- Tidak ada auto-learning dari percakapan.

## Scope

Extend sistem AllHaven yang sudah ada (FastAPI backend, Next.js frontend, Postgres DB) dengan:

1. **Persistent Memory System** — tabel `ai_memories` di Postgres.
2. **Memory Extraction Pipeline** — hybrid rule-based + LLM background extraction.
3. **Context Builder** — inject relevant memories ke setiap model request.
4. **Memory injected di semua 4 chat modes** (single, multi-agent, debate, reasoning).
5. **Memory API + Frontend UI** — lihat, edit, approve suggestions, toggle.
6. **Supabase optional sync** — background, tidak pernah block main flow.
7. **Tool Registry additions** — memory read/write tools untuk AI.

---

## Architecture

```
User Message
    ↓
[memory_context_builder.build()]        ← BARU
    → Profile + Preference memories (always)
    → Project memories (if relevant)
    → Section memories (if section match)
    → ~400-800 token cap
    ↓
System prompt + context block + history → Model (existing)
    ↓
Tool loop (existing, unchanged)
    ↓
Final assistant message persisted (existing)
    ↓
[memory_extraction_service.schedule_extraction()]   ← BARU (async, non-blocking)
    → Rule-based scan (instant)
    → LLM background call (if ambiguous)
    → Auto-save LOW sensitivity → ai_memories
    → Create pending → ai_memory_suggestions
    ↓
Response returned to frontend
```

---

## Database Schema

### `ai_memories`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| workspace_id | UUID | scoped, indexed |
| category | VARCHAR(50) | Profile \| Preferences \| Projects \| WorkStyle \| Technical \| Goals |
| title | VARCHAR(200) | short descriptor |
| content | TEXT | actual memory content |
| source | VARCHAR(30) | chat_extracted \| manual \| llm_extracted |
| status | VARCHAR(20) | active \| pending \| disabled \| stale |
| sensitivity | VARCHAR(10) | LOW \| MEDIUM \| HIGH |
| enabled | BOOL | user can toggle without deleting |
| confidence | FLOAT | 0.0-1.0 |
| relevance_score | FLOAT | updated on retrieval |
| last_used_at | TIMESTAMPTZ | |
| source_session_id | UUID \| null | |
| meta | JSONB | |
| created_at / updated_at | TIMESTAMPTZ | |

### `ai_memory_suggestions`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| workspace_id | UUID | |
| memory_id | UUID \| null | null=create, non-null=update existing |
| category | VARCHAR(50) | |
| title | VARCHAR(200) | |
| content | TEXT | |
| source_session_id | UUID | |
| source_snippet | VARCHAR(500) | what triggered extraction |
| confidence | FLOAT | |
| sensitivity | VARCHAR(10) | |
| extraction_method | VARCHAR(20) | rule_based \| llm |
| status | VARCHAR(20) | pending \| approved \| rejected \| auto_saved |
| created_at | TIMESTAMPTZ | |

### `ai_conversation_summaries`

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | |
| workspace_id | UUID | |
| session_id | UUID | unique per session |
| summary | TEXT | |
| message_count_at_summary | INT | when last summarized |
| created_at / updated_at | TIMESTAMPTZ | |

---

## Backend Services (New)

### `memory_service.py`
- CRUD for `ai_memories`
- `list_memories(db, principal, category, status)` → list
- `search_memories(db, principal, query)` → list
- `create_memory(db, principal, data)` → AiMemory
- `update_memory(db, principal, memory_id, data)` → AiMemory
- `delete_memory(db, principal, memory_id)` → None
- `set_enabled(db, principal, memory_id, enabled)` → AiMemory
- `approve_suggestion(db, principal, suggestion_id)` → AiMemory
- `reject_suggestion(db, principal, suggestion_id)` → None
- `list_suggestions(db, principal)` → list

### `memory_context_builder.py`
- `build(db, principal, message, section_key) → str | None`
  - Always: Profile + Preferences categories
  - Conditional: Projects (if message has project keywords)
  - Conditional: section-specific memories
  - Score: simple keyword overlap + category weights
  - Cap: ~800 tokens, most relevant first

### `memory_extraction_service.py`
- `schedule_extraction(db, principal, user_msg, assistant_response, session_id)`
  - Run `rule_based_extract()` synchronously
  - Dispatch LLM extraction as `asyncio.create_task()` if ambigu
- `rule_based_extract(text) → list[MemoryCandidate]`
  - Patterns: name, project, preferences, role, tech, goals
  - Sensitive detection: API key patterns, tokens → flag HIGH sensitivity
- `classify_sensitivity(candidate) → str`
- `deduplicate(db, principal, candidate) → AiMemory | None`
- `auto_save_or_suggest(db, principal, candidate)`:
  - LOW sensitivity + HIGH confidence → direct save to `ai_memories`
  - Otherwise → create `ai_memory_suggestions` (pending approval)
  - SECRET patterns → skip silently

### `supabase_sync_service.py` (optional)
- `is_enabled(db, principal) → bool`
- `sync_all(db, principal)` — background, never raises to caller
- Syncs: ai_memories, ai_memory_suggestions, chat_sessions, chat_messages, ai_tool_proposals, ai_multi_agent_runs
- Triggered after write operations if enabled

---

## Backend Services (Modified)

All 4 chat services inject context before request and trigger extraction after response:
- `ai_service.py` → `chat()`
- `ai_multi_service.py` → `multi_chat()`
- `ai_debate_service.py` → `debate_chat()`
- `ai_reasoning_service.py` → `reasoning_chat()`

The `section_key` is passed from the frontend with each request (already in the chat request schema or added to it).

---

## Tool Registry Additions

New **read** tools (auto-execute):
- `list_memories` — list memories by category
- `search_memories` — full-text search memories
- `get_section_memory` — memory for specific section key

New **write** tools (pending approval):
- `create_memory` — LOW risk
- `update_memory` — LOW risk
- `delete_memory` — MEDIUM risk

---

## API Endpoints (New Router `/ai/memory`)

```
GET    /ai/memory                  list_memories (with category/status filters)
POST   /ai/memory                  create_memory (manual)
GET    /ai/memory/search?q=        search_memories
GET    /ai/memory/suggestions      list_suggestions
PATCH  /ai/memory/{id}             update_memory
DELETE /ai/memory/{id}             delete_memory
POST   /ai/memory/{id}/enable      enable memory
POST   /ai/memory/{id}/disable     disable memory
POST   /ai/memory/suggestions/{id}/approve  approve suggestion
POST   /ai/memory/suggestions/{id}/reject   reject suggestion
POST   /ai/memory/sync/supabase    trigger Supabase sync (if enabled)
GET    /ai/memory/settings         get auto-learning settings
PUT    /ai/memory/settings         update auto-learning settings
```

---

## Frontend

### New Page: `/dashboard/ai/memory`
- Tabs: All | Auto-learned | Manual | Pending Suggestions
- Category filter sidebar
- Search box
- Memory card: title, content, category badge, source badge, enabled toggle, edit, delete
- Pending suggestions: source snippet, confidence, Approve/Reject/Edit buttons
- Settings: Auto-learning ON/OFF, Require approval for sensitive ON/OFF
- Clear all button (with confirmation)

### Chat Page Updates
- Memory indicator in header (subtle badge): "🧠 Memory updated" / "⏳ N pending"
- `section_key` sent with every chat request

### API Layer (`lib/api.ts`)
- `memoryApi` object with all endpoint calls

---

## Extraction Rules

**Auto-save (LOW sensitivity):**
- "nama saya X" → Profile / User name / "User's name is X"
- "project saya X" → Projects / Current project / "User's active project is X"
- "saya suka jawaban Y" → Preferences / Response style / "User prefers Y responses"
- "saya bekerja sebagai X" → Profile / User role / "User's role is X"
- "tech stack saya X" → Technical / Tech stack / "User uses X"

**Suggest (MEDIUM/HIGH sensitivity):**
- Financial data → MEDIUM
- Personal address, phone → HIGH
- Info about other people → HIGH

**BLOCK/REDACT (never save):**
- API key patterns: `sk-...`, `Bearer ...`, `ghp_...`, AWS keys
- Passwords, tokens, secrets in "key=value" form
- JWTs (`eyJ...`)
- Long opaque strings ≥32 chars that look like secrets

---

## Acceptance Tests

| Test | Input | Expected |
|------|-------|----------|
| A | "nama saya Joshua" → new chat → "siapa nama saya?" | AI: "Joshua" |
| B | "saya suka jawaban singkat dan tajam" → ask advice | AI responses become sharper |
| C | "API key saya adalah sk-xxx" | Memory NOT saved; no leakage |
| D | "project saya Haven" → "project apa yang sedang saya kerjakan?" | AI: "Haven" |
| E | Disable memory → ask about name | AI does not use memory |
| F | Finance summary test (existing tool) | `finance_monthly_summary` tool called |
| G | Calendar test (existing tool) | `list_events` tool called |

---

## Migration

New Alembic migration: `0007_ai_memories.py`
- Creates: `ai_memories`, `ai_memory_suggestions`, `ai_conversation_summaries`
- Backward compatible (no existing table changes)

---

## Supabase Sync

- Optional: configured in Settings → AI → Supabase
- Requires: SUPABASE_URL, SUPABASE_ANON_KEY (stored as integration config, encrypted at rest)
- Sync direction: local Postgres → Supabase (one-way for now)
- Never blocks: all sync errors logged silently
- Default: disabled
