# AI Tool Policy

**Core rule: AI proposes, a human approves, the backend executes.**

The AI assistant may **never** directly create, update, delete, move, upload, spend, schedule, or
execute workflows. It can only produce a *proposal* that a human reviews.

## What the MVP implements

- **Chat persistence:** `chat_sessions` and `chat_messages` store the conversation.
- **Honest replies:** `llm_service` returns a clear *"not configured"* message when
  `OLLAMA_BASE_URL` is not set. If it is set, the MVP still returns an honest *"live generation is
  disabled in this MVP"* message rather than faking model output. **No response is ever fabricated.**
- **Tool proposals:** the `ai_tool_proposals` table and schema exist. Proposals can be **listed**
  (`GET /ai/proposals`) and **rejected** (`POST /ai/proposals/{id}/reject`).

## What the MVP intentionally does NOT implement

- **No approve/execute endpoint.** There is deliberately no route that executes a proposal. This
  prevents any path to autonomous AI writes in the MVP.
- **No live LLM generation**, no fake tool execution, no AI-issued SQL or integration calls.

## Intended full flow (for when execution is added later)

1. User sends a natural-language message.
2. Backend persists the user message and calls the LLM service.
3. The LLM returns either a plain answer or a structured tool proposal.
4. Backend validates the proposal against a strict Pydantic schema and stores it as `PENDING`.
5. The frontend shows a confirmation card with the proposed action and its risk level.
6. The user **approves or rejects**.
7. Only on approval does the backend execute — **through the service layer**, never from raw LLM
   output — and write an audit log entry.

## Allowed proposal tools (future)

`create_task`, `create_note`, `create_transaction`, `summarize_notes`,
`suggest_schedule_without_calendar_write`.

## Forbidden (always require explicit confirmation, never automatic)

Deleting anything, executing n8n workflows, sending email, moving money, financial/investment
advice, calendar writes, file deletes.

## Risk levels

Proposals carry a `risk_level` (`LOW` / `MEDIUM` / `HIGH`) and `requires_confirmation` (always
`true` in the MVP). The UI surfaces these so a human always has full context before acting.
