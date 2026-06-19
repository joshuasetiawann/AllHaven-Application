"""Central AI Tool Registry — the ONLY bridge between models and app modules.

Security model (enforced here, not trusted to the model):
    * Tool names are a fixed allowlist; unknown tools are rejected.
    * Arguments are validated (Pydantic schemas / explicit parsing) per tool.
    * READ tools execute immediately and only return workspace-scoped data via
      the existing module services (which enforce scoping themselves).
    * WRITE tools never execute directly from a model turn: they create a
      PENDING ``AiToolProposal`` for human approval. When the workspace turns
      ``require_approval`` off, LOW/MEDIUM writes may auto-execute, but
      HIGH-risk tools (deletes of files, enabling workflows, service control)
      ALWAYS require approval.
    * Every call — executed, pending, or failed — is written to the audit log.
    * The model's output is never trusted: results are built from real service
      returns, and a pending action is reported as pending, never as done.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Optional

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException, NotFoundError, ValidationAppError
from app.core.principal import Principal
from app.domain.ai import AiToolProposal
from app.services import ai_settings_service
from app.services.audit_service import write_audit

MAX_LIST_ITEMS = 25  # keep tool results small enough for model context


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    module: str
    access: str  # "read" | "write"
    risk: str    # "LOW" | "MEDIUM" | "HIGH"
    parameters: dict
    handler: Callable[[Session, Principal, dict], dict]

    @property
    def approval_required(self) -> bool:
        return self.access == "write"


class ToolError(Exception):
    """A safe, user-showable tool failure."""


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _iso(value) -> Optional[str]:
    return value.isoformat() if value is not None and hasattr(value, "isoformat") else value


def _uuid(value, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        raise ToolError(f"'{label}' must be a valid id.")


def _schema(properties: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


def _str_prop(desc: str) -> dict:
    return {"type": "string", "description": desc}


# --------------------------------------------------------------------------- #
# serializers (small, model-friendly dicts — never raw ORM rows)
# --------------------------------------------------------------------------- #


def _task(t) -> dict:
    return {"id": str(t.id), "title": t.title, "status": t.status, "priority": t.priority,
            "due_at": _iso(t.due_at), "completed_at": _iso(t.completed_at)}


def _note(n, with_content: bool = False) -> dict:
    out = {"id": str(n.id), "title": n.title, "tags": list(n.tags or []),
           "is_pinned": bool(n.is_pinned), "updated_at": _iso(n.updated_at)}
    if with_content:
        out["content"] = (n.content or "")[:2000]
    return out


def _event(e) -> dict:
    return {"id": str(e.id), "title": e.title, "location": e.location, "all_day": bool(e.all_day),
            "start_at": _iso(e.start_at), "end_at": _iso(e.end_at)}


def _txn(t) -> dict:
    return {"id": str(t.id), "type": t.type, "amount": float(t.amount), "currency": t.currency,
            "description": t.description, "transaction_date": _iso(t.transaction_date),
            "category": t.category_name_snapshot}


def _file(f) -> dict:
    return {"id": str(f.id), "filename": f.filename, "content_type": f.content_type,
            "size_bytes": f.size_bytes, "created_at": _iso(f.created_at)}


def _automation(a) -> dict:
    return {"id": str(a.id), "name": a.name, "description": a.description, "enabled": bool(a.enabled),
            "trigger_type": a.trigger_type, "action_type": a.action_type}


# --------------------------------------------------------------------------- #
# handlers — time
# --------------------------------------------------------------------------- #


def _h_current_time(db, principal, args) -> dict:
    now = datetime.now().astimezone()
    return {"iso": now.isoformat(), "date": now.date().isoformat(),
            "time": now.strftime("%H:%M:%S"), "timezone": str(now.tzinfo),
            "utc_offset": now.strftime("%z")}


# --------------------------------------------------------------------------- #
# handlers — tasks
# --------------------------------------------------------------------------- #


def _h_list_tasks(db, principal, args) -> dict:
    from app.services import task_service

    rows = task_service.list_tasks(db, principal, status=args.get("status"), limit=MAX_LIST_ITEMS, offset=0)
    return {"tasks": [_task(t) for t in rows], "count": len(rows)}


def _h_create_task(db, principal, args) -> dict:
    from app.schemas.tasks import TaskCreate
    from app.services import task_service

    task = task_service.create_task(db, principal, TaskCreate(**args))
    return {"task": _task(task)}


def _h_update_task(db, principal, args) -> dict:
    from app.schemas.tasks import TaskUpdate
    from app.services import task_service

    task_id = _uuid(args.pop("task_id", None), "task_id")
    task = task_service.update_task(db, principal, task_id, TaskUpdate(**args))
    return {"task": _task(task)}


def _h_complete_task(db, principal, args) -> dict:
    from app.services import task_service

    task = task_service.set_completion(db, principal, _uuid(args.get("task_id"), "task_id"), done=True)
    return {"task": _task(task)}


def _h_delete_task(db, principal, args) -> dict:
    from app.services import task_service

    task_service.delete_task(db, principal, _uuid(args.get("task_id"), "task_id"))
    return {"deleted": True}


# --------------------------------------------------------------------------- #
# handlers — calendar
# --------------------------------------------------------------------------- #


def _h_list_events(db, principal, args) -> dict:
    from app.services import calendar_service

    rows = calendar_service.list_events(db, principal, start=args.get("start"), end=args.get("end"))
    rows = rows[:MAX_LIST_ITEMS]
    return {"events": [_event(e) for e in rows], "count": len(rows)}


def _h_create_event(db, principal, args) -> dict:
    from app.services import calendar_service

    event = calendar_service.create_event(db, principal, args)
    return {"event": _event(event)}


def _h_update_event(db, principal, args) -> dict:
    from app.services import calendar_service

    event_id = _uuid(args.pop("event_id", None), "event_id")
    event = calendar_service.update_event(db, principal, event_id, args)
    return {"event": _event(event)}


def _h_delete_event(db, principal, args) -> dict:
    from app.services import calendar_service

    calendar_service.delete_event(db, principal, _uuid(args.get("event_id"), "event_id"))
    return {"deleted": True}


# --------------------------------------------------------------------------- #
# handlers — notes
# --------------------------------------------------------------------------- #


def _h_list_notes(db, principal, args) -> dict:
    from app.services import note_service

    rows = note_service.list_notes(db, principal, q=args.get("q"), tag=args.get("tag"),
                                   limit=MAX_LIST_ITEMS, offset=0)
    return {"notes": [_note(n, with_content=bool(args.get("include_content"))) for n in rows],
            "count": len(rows)}


def _h_create_note(db, principal, args) -> dict:
    from app.schemas.notes import NoteCreate
    from app.services import note_service

    note = note_service.create_note(db, principal, NoteCreate(**args))
    return {"note": _note(note)}


def _h_update_note(db, principal, args) -> dict:
    from app.schemas.notes import NoteUpdate
    from app.services import note_service

    note_id = _uuid(args.pop("note_id", None), "note_id")
    note = note_service.update_note(db, principal, note_id, NoteUpdate(**args))
    return {"note": _note(note)}


def _h_delete_note(db, principal, args) -> dict:
    from app.services import note_service

    note_service.delete_note(db, principal, _uuid(args.get("note_id"), "note_id"))
    return {"deleted": True}


# --------------------------------------------------------------------------- #
# handlers — finance
# --------------------------------------------------------------------------- #


def _h_list_transactions(db, principal, args) -> dict:
    from app.services import finance_service

    rows = finance_service.list_transactions(db, principal, limit=MAX_LIST_ITEMS, offset=0)
    return {"transactions": [_txn(t) for t in rows], "count": len(rows)}


def _h_finance_summary(db, principal, args) -> dict:
    from app.services import finance_service

    now = datetime.now(timezone.utc)
    year = int(args.get("year") or now.year)
    month = int(args.get("month") or now.month)
    currency = str(args.get("currency") or "IDR")
    return finance_service.monthly_summary(db, principal, year=year, month=month, currency=currency)


def _h_list_categories(db, principal, args) -> dict:
    from app.services import finance_service

    rows = finance_service.list_categories(db, principal)
    return {"categories": [{"id": str(c.id), "name": c.name, "type": c.type} for c in rows]}


def _h_create_transaction(db, principal, args) -> dict:
    from app.schemas.finance import TransactionCreate
    from app.services import finance_service

    txn = finance_service.create_transaction(db, principal, TransactionCreate(**args))
    return {"transaction": _txn(txn)}


def _h_update_transaction(db, principal, args) -> dict:
    from app.schemas.finance import TransactionUpdate
    from app.services import finance_service

    txn_id = _uuid(args.pop("transaction_id", None), "transaction_id")
    txn = finance_service.update_transaction(db, principal, txn_id, TransactionUpdate(**args))
    return {"transaction": _txn(txn)}


def _h_delete_transaction(db, principal, args) -> dict:
    from app.services import finance_service

    finance_service.delete_transaction(db, principal, _uuid(args.get("transaction_id"), "transaction_id"))
    return {"deleted": True}


# --------------------------------------------------------------------------- #
# handlers — files (metadata only; never raw filesystem paths)
# --------------------------------------------------------------------------- #


def _h_list_files(db, principal, args) -> dict:
    from app.services import drive_service

    rows = drive_service.list_files(db, principal)[:MAX_LIST_ITEMS]
    return {"files": [_file(f) for f in rows], "count": len(rows)}


def _h_search_files(db, principal, args) -> dict:
    from app.services import drive_service

    q = str(args.get("q") or "").lower().strip()
    if not q:
        raise ToolError("Provide a search query 'q'.")
    rows = [f for f in drive_service.list_files(db, principal) if q in (f.filename or "").lower()]
    rows = rows[:MAX_LIST_ITEMS]
    return {"files": [_file(f) for f in rows], "count": len(rows)}


def _h_delete_file(db, principal, args) -> dict:
    from app.services import drive_service

    drive_service.delete_file(db, principal, _uuid(args.get("file_id"), "file_id"))
    return {"deleted": True}


# --------------------------------------------------------------------------- #
# handlers — weather
# --------------------------------------------------------------------------- #


def _h_current_weather(db, principal, args) -> dict:
    from app.services import weather_service

    return weather_service.current_weather(db, principal, location=args.get("location"))


# --------------------------------------------------------------------------- #
# handlers — AI memories (read from registry; write via proposals)
# --------------------------------------------------------------------------- #


def _h_list_memories(db, principal, args) -> dict:
    from app.services import memory_service

    category = args.get("category")
    rows = memory_service.list_memories(db, principal, category=category, enabled_only=True, limit=20)
    return {
        "memories": [
            {"id": str(m.id), "category": m.category, "title": m.title,
             "content": m.content, "source": m.source}
            for m in rows
        ],
        "count": len(rows),
    }


def _h_search_memories(db, principal, args) -> dict:
    from app.services import memory_service

    q = str(args.get("q") or "").strip()
    if not q:
        raise ToolError("Provide a search query 'q'.")
    rows = memory_service.search_memories(db, principal, q, limit=10)
    return {
        "memories": [
            {"id": str(m.id), "category": m.category, "title": m.title, "content": m.content}
            for m in rows
        ],
        "count": len(rows),
    }


def _h_create_memory_tool(db, principal, args) -> dict:
    from app.domain.ai_memory import MEMORY_CATEGORIES
    from app.services import memory_service

    title = str(args.get("title") or "").strip()
    if not title:
        raise ToolError("Provide 'title'.")
    content = str(args.get("content") or "").strip()
    if not content:
        raise ToolError("Provide 'content'.")
    category = str(args.get("category") or "Profile").strip() or "Profile"
    if category not in MEMORY_CATEGORIES:
        raise ToolError(
            f"Invalid category '{category}'. Valid values: {', '.join(MEMORY_CATEGORIES)}."
        )

    m = memory_service.upsert_memory(
        db, principal,
        category=category,
        title=title,
        content=content,
        source="manual",
        sensitivity="LOW",
        confidence=1.0,
    )
    return {"memory": {"id": str(m.id), "category": m.category, "title": m.title, "content": m.content}}


def _h_update_memory_tool(db, principal, args) -> dict:
    from app.services import memory_service

    memory_id = _uuid(args.get("memory_id"), "memory_id")
    m = memory_service.update_memory(
        db, principal, memory_id,
        title=args.get("title"),
        content=args.get("content"),
    )
    return {"memory": {"id": str(m.id), "title": m.title, "content": m.content}}


def _h_delete_memory_tool(db, principal, args) -> dict:
    from app.services import memory_service

    memory_id = _uuid(args.get("memory_id"), "memory_id")
    memory_service.delete_memory(db, principal, memory_id)
    return {"deleted": True}


# --------------------------------------------------------------------------- #
# handlers — automations / workflows (drafts only; never auto-run)
# --------------------------------------------------------------------------- #


def _h_list_workflows(db, principal, args) -> dict:
    from app.services import automation_service

    rows = automation_service.list_automations(db, principal)[:MAX_LIST_ITEMS]
    return {"workflows": [_automation(a) for a in rows], "count": len(rows)}


def _h_create_workflow_draft(db, principal, args) -> dict:
    from app.services import automation_service

    row = automation_service.create_automation(db, principal, {
        "name": args.get("name"), "description": args.get("description"),
        "trigger_type": args.get("trigger_type") or "manual",
        "action_type": args.get("action_type") or "noop",
        "config": args.get("config") or {},
    })
    return {"workflow": _automation(row), "note": "Draft created. Drafts are never auto-executed."}


def _h_update_workflow_draft(db, principal, args) -> dict:
    from app.services import automation_service

    automation_id = _uuid(args.pop("workflow_id", None), "workflow_id")
    row = automation_service.update_automation(db, principal, automation_id, args)
    return {"workflow": _automation(row)}


def _h_set_workflow_enabled(enabled: bool):
    def handler(db, principal, args) -> dict:
        from app.services import automation_service

        automation_id = _uuid(args.get("workflow_id"), "workflow_id")
        row = automation_service.update_automation(db, principal, automation_id, {"enabled": enabled})
        return {"workflow": _automation(row)}

    return handler


# --------------------------------------------------------------------------- #
# handlers — system control (proxied to the token-gated local agent)
# --------------------------------------------------------------------------- #


def _h_service_status(db, principal, args) -> dict:
    from app.services import system_service

    status = system_service.get_status()
    return {"agent_running": status.get("agent", {}).get("running", False),
            "services": [{k: s.get(k) for k in ("name", "label", "status", "port")}
                         for s in status.get("services", [])]}


def _h_service_logs(db, principal, args) -> dict:
    from app.services import system_service

    name = str(args.get("service") or "")
    logs = system_service.get_logs(name, lines=min(int(args.get("lines") or 100), 200))
    return {"service": name, "logs": logs.get("content", "")[-4000:], "message": logs.get("message", "")}


def _h_service_action(action: str):
    def handler(db, principal, args) -> dict:
        from app.services import system_service

        name = str(args.get("service") or "")
        result = system_service.do_action(name, action)
        return {"service": result}

    return handler


# --------------------------------------------------------------------------- #
# THE REGISTRY (fixed allowlist — nothing outside this can ever be called)
# --------------------------------------------------------------------------- #

_TASK_FIELDS = {
    "title": _str_prop("Task title"),
    "description": _str_prop("Optional details"),
    "status": {"type": "string", "enum": ["TODO", "IN_PROGRESS", "DONE"]},
    "priority": {"type": "string", "enum": ["LOW", "NORMAL", "HIGH", "URGENT"]},
    "due_at": _str_prop("Due date-time, ISO 8601 (e.g. 2026-06-12T09:00:00)"),
}
_EVENT_FIELDS = {
    "title": _str_prop("Event title"),
    "description": _str_prop("Optional details"),
    "location": _str_prop("Optional location"),
    "start_at": _str_prop("Start, ISO 8601"),
    "end_at": _str_prop("End, ISO 8601 (optional)"),
    "all_day": {"type": "boolean"},
}
_TXN_FIELDS = {
    "type": {"type": "string", "enum": ["INCOME", "EXPENSE"]},
    "amount": {"type": "number", "description": "Positive amount"},
    "currency": _str_prop("Currency code, default IDR"),
    "description": _str_prop("What this was for"),
    "transaction_date": _str_prop("Date, YYYY-MM-DD"),
    "category_id": _str_prop("Optional category id (see list_finance_categories)"),
}

TOOLS: dict[str, ToolSpec] = {t.name: t for t in (
    # --- time (read) ---
    ToolSpec("get_current_time", "Current local date, time, and timezone.", "time", "read", "LOW",
             _schema({}), _h_current_time),
    # --- tasks ---
    ToolSpec("list_tasks", "List the user's tasks (optionally by status).", "tasks", "read", "LOW",
             _schema({"status": {"type": "string", "enum": ["TODO", "IN_PROGRESS", "DONE"]}}), _h_list_tasks),
    ToolSpec("create_task", "Create a task.", "tasks", "write", "LOW",
             _schema(_TASK_FIELDS, ["title"]), _h_create_task),
    ToolSpec("update_task", "Update a task's fields.", "tasks", "write", "LOW",
             _schema({"task_id": _str_prop("Task id"), **_TASK_FIELDS}, ["task_id"]), _h_update_task),
    ToolSpec("complete_task", "Mark a task as done.", "tasks", "write", "LOW",
             _schema({"task_id": _str_prop("Task id")}, ["task_id"]), _h_complete_task),
    ToolSpec("delete_task", "Delete a task.", "tasks", "write", "MEDIUM",
             _schema({"task_id": _str_prop("Task id")}, ["task_id"]), _h_delete_task),
    # --- calendar ---
    ToolSpec("list_events", "List calendar events (optional ISO start/end range).", "calendar", "read", "LOW",
             _schema({"start": _str_prop("Range start, ISO"), "end": _str_prop("Range end, ISO")}), _h_list_events),
    ToolSpec("create_event", "Create a calendar event.", "calendar", "write", "LOW",
             _schema(_EVENT_FIELDS, ["title", "start_at"]), _h_create_event),
    ToolSpec("update_event", "Update a calendar event.", "calendar", "write", "LOW",
             _schema({"event_id": _str_prop("Event id"), **_EVENT_FIELDS}, ["event_id"]), _h_update_event),
    ToolSpec("delete_event", "Delete a calendar event.", "calendar", "write", "MEDIUM",
             _schema({"event_id": _str_prop("Event id")}, ["event_id"]), _h_delete_event),
    # --- notes ---
    ToolSpec("list_notes", "List recent notes (optionally filter by tag).", "notes", "read", "LOW",
             _schema({"tag": _str_prop("Filter by tag"),
                      "include_content": {"type": "boolean", "description": "Include note text"}}), _h_list_notes),
    ToolSpec("search_notes", "Search notes by text query.", "notes", "read", "LOW",
             _schema({"q": _str_prop("Search query"),
                      "include_content": {"type": "boolean"}}, ["q"]), _h_list_notes),
    ToolSpec("create_note", "Create a note.", "notes", "write", "LOW",
             _schema({"title": _str_prop("Note title"), "content": _str_prop("Note body"),
                      "tags": {"type": "array", "items": {"type": "string"}}}, ["title"]), _h_create_note),
    ToolSpec("update_note", "Update a note.", "notes", "write", "LOW",
             _schema({"note_id": _str_prop("Note id"), "title": _str_prop("New title"),
                      "content": _str_prop("New body"),
                      "tags": {"type": "array", "items": {"type": "string"}}}, ["note_id"]), _h_update_note),
    ToolSpec("delete_note", "Delete a note.", "notes", "write", "MEDIUM",
             _schema({"note_id": _str_prop("Note id")}, ["note_id"]), _h_delete_note),
    # --- finance ---
    ToolSpec("list_transactions", "List recent finance transactions.", "finance", "read", "LOW",
             _schema({}), _h_list_transactions),
    ToolSpec("finance_monthly_summary", "Income/expense/balance summary for a month.", "finance", "read", "LOW",
             _schema({"year": {"type": "integer"}, "month": {"type": "integer"},
                      "currency": _str_prop("Currency code, default IDR")}), _h_finance_summary),
    ToolSpec("list_finance_categories", "List finance categories (for create_transaction).", "finance", "read", "LOW",
             _schema({}), _h_list_categories),
    ToolSpec("create_transaction", "Record an income/expense transaction.", "finance", "write", "MEDIUM",
             _schema(_TXN_FIELDS, ["type", "amount", "transaction_date"]), _h_create_transaction),
    ToolSpec("update_transaction", "Update a transaction.", "finance", "write", "MEDIUM",
             _schema({"transaction_id": _str_prop("Transaction id"), **_TXN_FIELDS},
                     ["transaction_id"]), _h_update_transaction),
    ToolSpec("delete_transaction", "Delete a transaction.", "finance", "write", "MEDIUM",
             _schema({"transaction_id": _str_prop("Transaction id")}, ["transaction_id"]), _h_delete_transaction),
    # --- files (metadata only) ---
    ToolSpec("list_files", "List stored files (metadata only).", "files", "read", "LOW",
             _schema({}), _h_list_files),
    ToolSpec("search_files", "Search stored files by name (metadata only).", "files", "read", "LOW",
             _schema({"q": _str_prop("Filename query")}, ["q"]), _h_search_files),
    ToolSpec("delete_file", "Delete a stored file.", "files", "write", "HIGH",
             _schema({"file_id": _str_prop("File id")}, ["file_id"]), _h_delete_file),
    # --- weather ---
    ToolSpec("get_current_weather", "Current weather (honest 'setup_required' if no provider).",
             "weather", "read", "LOW",
             _schema({"location": _str_prop("Location name (optional; default saved location)")}),
             _h_current_weather),
    # --- automations / workflows ---
    ToolSpec("list_workflows", "List automation workflow drafts.", "automation", "read", "LOW",
             _schema({}), _h_list_workflows),
    ToolSpec("create_workflow_draft", "Create an automation DRAFT (never auto-executed).",
             "automation", "write", "LOW",
             _schema({"name": _str_prop("Workflow name"), "description": _str_prop("What it does"),
                      "trigger_type": _str_prop("e.g. schedule, task_created"),
                      "action_type": _str_prop("e.g. notify, webhook, email"),
                      "config": {"type": "object", "additionalProperties": True}}, ["name"]),
             _h_create_workflow_draft),
    ToolSpec("update_workflow_draft", "Update an automation draft.", "automation", "write", "LOW",
             _schema({"workflow_id": _str_prop("Workflow id"), "name": _str_prop("New name"),
                      "description": _str_prop("New description")}, ["workflow_id"]),
             _h_update_workflow_draft),
    ToolSpec("enable_workflow", "Enable a workflow (risky — requires approval).", "automation", "write", "HIGH",
             _schema({"workflow_id": _str_prop("Workflow id")}, ["workflow_id"]),
             _h_set_workflow_enabled(True)),
    ToolSpec("disable_workflow", "Disable a workflow.", "automation", "write", "LOW",
             _schema({"workflow_id": _str_prop("Workflow id")}, ["workflow_id"]),
             _h_set_workflow_enabled(False)),
    # --- AI memories ---
    ToolSpec("list_memories", "List the user's AI memories (optionally by category).", "memory", "read", "LOW",
             _schema({"category": _str_prop("Category: Profile|Preferences|Projects|WorkStyle|Technical|Goals")}),
             _h_list_memories),
    ToolSpec("search_memories", "Search AI memories by keyword.", "memory", "read", "LOW",
             _schema({"q": _str_prop("Search query")}, ["q"]),
             _h_search_memories),
    ToolSpec("create_memory", "Create an AI memory for the user.", "memory", "write", "LOW",
             _schema({
                 "category": _str_prop("Profile|Preferences|Projects|WorkStyle|Technical|Goals"),
                 "title": _str_prop("Short descriptor (max 50 chars)"),
                 "content": _str_prop("Complete sentence describing the memory"),
             }, ["category", "title", "content"]),
             _h_create_memory_tool),
    ToolSpec("update_memory", "Update an existing AI memory.", "memory", "write", "LOW",
             _schema({
                 "memory_id": _str_prop("Memory id"),
                 "title": _str_prop("New title"),
                 "content": _str_prop("New content"),
             }, ["memory_id"]),
             _h_update_memory_tool),
    ToolSpec("delete_memory", "Delete an AI memory.", "memory", "write", "MEDIUM",
             _schema({"memory_id": _str_prop("Memory id")}, ["memory_id"]),
             _h_delete_memory_tool),
    # --- system control (allowlisted services/actions; agent-proxied) ---
    ToolSpec("get_service_status", "Status of Haven services (backend, frontend, database…).",
             "system", "read", "LOW", _schema({}), _h_service_status),
    ToolSpec("get_service_logs", "Recent (masked) logs of one service.", "system", "read", "MEDIUM",
             _schema({"service": _str_prop("Service name (backend, frontend, postgres…)"),
                      "lines": {"type": "integer", "minimum": 10, "maximum": 200}}, ["service"]),
             _h_service_logs),
    ToolSpec("restart_service", "Restart a Haven service (requires approval).", "system", "write", "HIGH",
             _schema({"service": _str_prop("Service name")}, ["service"]), _h_service_action("restart")),
    ToolSpec("start_service", "Start a Haven service (requires approval).", "system", "write", "HIGH",
             _schema({"service": _str_prop("Service name")}, ["service"]), _h_service_action("start")),
    ToolSpec("stop_service", "Stop a Haven service (requires approval).", "system", "write", "HIGH",
             _schema({"service": _str_prop("Service name")}, ["service"]), _h_service_action("stop")),
)}


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #


def list_tools_view(db: Session, principal: Principal) -> list[dict]:
    disabled = ai_settings_service.disabled_tools(db, principal)
    return [{
        "name": t.name, "description": t.description, "module": t.module,
        "access": t.access, "risk": t.risk,
        "approval_required": t.approval_required,
        "enabled": t.name not in disabled,
    } for t in TOOLS.values()]


def tool_definitions(db: Session, principal: Principal) -> list[dict]:
    """OpenAI 'tools' array for all enabled tools."""
    disabled = ai_settings_service.disabled_tools(db, principal)
    return [{
        "type": "function",
        "function": {"name": t.name, "description": t.description, "parameters": t.parameters},
    } for t in TOOLS.values() if t.name not in disabled]


def _execute(db: Session, principal: Principal, spec: ToolSpec, args: dict) -> dict:
    try:
        return spec.handler(db, principal, dict(args or {}))
    except ToolError as exc:
        raise
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else {}
        raise ToolError(f"Invalid arguments: {first.get('loc', ('?',))[0]} — {first.get('msg', 'invalid')}")
    except AppException as exc:
        raise ToolError(str(getattr(exc, "message", exc))[:300])
    except (TypeError, ValueError, KeyError) as exc:
        raise ToolError(f"Invalid arguments: {str(exc)[:200]}")


def _audit_call(db, principal, tool: str, args: dict, status: str, extra: dict | None = None) -> None:
    write_audit(
        db, action="AI_TOOL_CALL", entity_name="ai_tool",
        workspace_id=principal.workspace_id, user_id=principal.user_id,
        meta={"tool": tool, "args": args, "status": status, **(extra or {})},
    )


def run_tool_call(db: Session, principal: Principal, name: str, args: dict) -> dict:
    """Validate + run one model-requested tool call. Returns an outcome dict the
    model can read; NEVER raises (failures are honest outcomes)."""
    spec = TOOLS.get(name)
    if spec is None:
        return {"status": "error", "tool": name, "error": f"Unknown tool '{name}'. Only registered tools exist."}
    if not isinstance(args, dict):
        return {"status": "error", "tool": name, "error": "Tool arguments must be an object."}
    if not ai_settings_service.is_tool_enabled(db, principal, name):
        _audit_call(db, principal, name, args, "disabled")
        return {"status": "error", "tool": name, "error": f"The tool '{name}' is disabled in Settings → AI Tools."}

    if spec.access == "read":
        try:
            result = _execute(db, principal, spec, args)
        except ToolError as exc:
            _audit_call(db, principal, name, args, "error", {"error": str(exc)})
            return {"status": "error", "tool": name, "error": str(exc)}
        _audit_call(db, principal, name, args, "executed")
        return {"status": "executed", "tool": name, "result": result}

    # WRITE: pending approval by default; HIGH risk always needs approval.
    needs_approval = ai_settings_service.approval_required(db, principal) or spec.risk == "HIGH"
    if needs_approval:
        proposal = AiToolProposal(
            workspace_id=principal.workspace_id,
            created_by=principal.user_id,
            tool_name=name,
            tool_payload=dict(args or {}),
            status="PENDING",
            risk_level=spec.risk,
            requires_confirmation=True,
        )
        db.add(proposal)
        db.flush()
        _audit_call(db, principal, name, args, "pending_approval", {"proposal_id": str(proposal.id)})
        return {
            "status": "pending_approval", "tool": name,
            "proposal_id": str(proposal.id), "risk": spec.risk,
            "note": ("A pending action was created and is awaiting HUMAN APPROVAL. "
                     "It has NOT been executed — tell the user to approve it in the Pending actions panel."),
        }
    try:
        result = _execute(db, principal, spec, args)
    except ToolError as exc:
        _audit_call(db, principal, name, args, "error", {"error": str(exc)})
        return {"status": "error", "tool": name, "error": str(exc)}
    _audit_call(db, principal, name, args, "executed", {"approval": "auto (workspace setting)"})
    return {"status": "executed", "tool": name, "result": result}


def approve_proposal(db: Session, principal: Principal, proposal_id: uuid.UUID) -> dict:
    """Execute a PENDING proposal after explicit human approval."""
    proposal = db.scalar(select(AiToolProposal).where(
        AiToolProposal.id == proposal_id,
        AiToolProposal.workspace_id == principal.workspace_id,
    ))
    if not proposal:
        raise NotFoundError("Tool proposal not found.")
    if proposal.status != "PENDING":
        raise ValidationAppError(f"This proposal is already {proposal.status.lower()}.")
    spec = TOOLS.get(proposal.tool_name)
    if spec is None:
        raise ValidationAppError(f"Tool '{proposal.tool_name}' no longer exists.")

    try:
        result = _execute(db, principal, spec, dict(proposal.tool_payload or {}))
    except ToolError as exc:
        _audit_call(db, principal, proposal.tool_name, dict(proposal.tool_payload or {}),
                    "approve_failed", {"proposal_id": str(proposal.id), "error": str(exc)})
        db.commit()
        raise ValidationAppError(f"Approved, but execution failed: {exc}")

    proposal.status = "EXECUTED"
    proposal.executed_at = datetime.now(timezone.utc)
    db.flush()
    _audit_call(db, principal, proposal.tool_name, dict(proposal.tool_payload or {}),
                "approved_executed", {"proposal_id": str(proposal.id)})
    db.commit()
    db.refresh(proposal)
    return {"proposal": proposal, "result": result}


def edit_proposal(db: Session, principal: Principal, proposal_id: uuid.UUID, tool_payload: dict) -> AiToolProposal:
    """Edit a PENDING proposal's payload before approving it."""
    proposal = db.scalar(select(AiToolProposal).where(
        AiToolProposal.id == proposal_id,
        AiToolProposal.workspace_id == principal.workspace_id,
    ))
    if not proposal:
        raise NotFoundError("Tool proposal not found.")
    if proposal.status != "PENDING":
        raise ValidationAppError("Only pending proposals can be edited.")
    if not isinstance(tool_payload, dict):
        raise ValidationAppError("tool_payload must be an object.")
    proposal.tool_payload = tool_payload
    db.flush()
    write_audit(db, action="UPDATE", entity_name="ai_tool_proposal",
                workspace_id=principal.workspace_id, user_id=principal.user_id,
                entity_id=proposal.id, meta={"change": "payload_edited_by_user"})
    db.commit()
    db.refresh(proposal)
    return proposal
