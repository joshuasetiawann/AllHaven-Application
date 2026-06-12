# AI Tool Policy

**Core rule: AI proposes, a human approves, the backend executes.**

The AI assistant may **never** directly create, update, delete, move, upload, spend, schedule, or
execute workflows. It can only request actions through the backend **Tool Registry**; write
actions become *proposals* that a human reviews.

## What is implemented (since v0.12.0)

- **Chat persistence:** `chat_sessions` and `chat_messages` store the conversation
  (single-agent chat is history-aware).
- **Honest replies:** providers return clear *"not configured" / "disabled" / "blocked"*
  statuses. **No response is ever fabricated.**
- **Tool Registry** (`app/services/ai_tools_registry.py`): a fixed allowlist of ~40 tools across
  time, tasks, calendar, notes, finance, files (metadata only), weather, automations, memory, and
  system control. Unknown tools or malformed arguments are rejected and audited. The model never
  touches the DB, shell, or filesystem — only module services that enforce workspace scoping.
- **Read tools execute immediately** (e.g. `list_tasks`, `finance_monthly_summary`,
  `get_current_weather`, `get_service_status`). Results come from real services only.
- **Write tools create `PENDING` proposals** (`ai_tool_proposals`). They are **never executed in
  the model's turn**, and the model is told — and the registry result enforces — that a pending
  action is *not done*.
- **Approval endpoints:** `GET /ai/proposals` (list pending),
  `POST /ai/proposals/{id}/approve` (executes **through the service layer** via the registry,
  marks `EXECUTED`, audits), `PATCH /ai/proposals/{id}` (edit the payload while pending),
  `POST /ai/proposals/{id}/reject` (does nothing else).
- **Audit log:** every tool call — executed, pending, approved, rejected, or failed — is written
  to the append-only audit log.

## The flow

1. User sends a natural-language message.
2. Backend persists the user message and calls the configured provider with the registry's tool
   definitions (native tool calling on the OpenAI-compatible family; other providers chat
   without tools — honestly).
3. The model may request tools. Each request is validated against the allowlist + schema.
4. Reads execute; writes are stored as `PENDING` proposals with a risk level.
5. The chat UI shows tool activity chips and a **Pending actions** panel (Approve / Edit /
   Reject) with the exact data to be changed and its risk level.
6. Only on **human approval** does the backend execute — through the service layer, never from
   raw LLM output — and write an audit entry.

## Approval policy

- `require_approval` defaults to **ON** (Settings → AI Chat). All writes await approval.
- If a workspace turns it off, LOW/MEDIUM writes may auto-execute, **but HIGH-risk tools always
  require approval**: deleting files, enabling workflows, and service start/stop/restart.
- Per-tool enable/disable lives in **Settings → AI Tools**; disabled tools refuse to run.

## Forbidden (never expressible through the registry)

Arbitrary shell commands or SQL, raw filesystem paths, reading secret values, executing n8n
workflows directly, sending email, moving money, financial/investment advice. Automations are
**drafts** — the AI cannot silently enable risky automation (enabling is HIGH-risk → approval).

## Risk levels

Proposals carry a `risk_level` (`LOW` / `MEDIUM` / `HIGH`) and `requires_confirmation`. The UI
surfaces these so a human always has full context before acting.
