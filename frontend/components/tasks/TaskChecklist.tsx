"use client";

import { useState } from "react";
import { Check, Plus, X } from "lucide-react";
import { tasksApi } from "@/lib/api";
import { cn } from "@/lib/format";
import type { Task } from "@/types";

const MAX_ITEMS = 5;

export function TaskChecklist({ task, onChange }: { task: Task; onChange: (t: Task) => void }) {
  const [newItem, setNewItem] = useState("");
  const [busy, setBusy] = useState(false);
  const items = task.checklist_items ?? [];
  const done = items.filter((i) => i.is_done).length;
  const pct = items.length ? Math.round((done / items.length) * 100) : 0;

  const toggle = async (itemId: string, isDone: boolean) => {
    onChange({
      ...task,
      checklist_items: items.map((i) => (i.id === itemId ? { ...i, is_done: isDone } : i)),
    });
    try {
      onChange(await tasksApi.updateChecklistItem(task.id, itemId, { is_done: isDone }));
    } catch {
      /* revert on next refresh */
    }
  };

  const remove = async (itemId: string) => {
    onChange({ ...task, checklist_items: items.filter((i) => i.id !== itemId) });
    try {
      onChange(await tasksApi.deleteChecklistItem(task.id, itemId));
    } catch {
      /* ignore */
    }
  };

  const add = async () => {
    const title = newItem.trim();
    if (!title || items.length >= MAX_ITEMS || busy) return;
    setBusy(true);
    try {
      onChange(await tasksApi.addChecklistItem(task.id, title));
      setNewItem("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-3 rounded-lg border border-border bg-surface-input/50 p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-mono text-[11px] uppercase tracking-wide text-content-subtle">
          Command checklist · {done}/{items.length || 0}
        </span>
        <span className="text-[11px] text-content-subtle">max {MAX_ITEMS}</span>
      </div>
      <div className="mb-3 h-1.5 w-full overflow-hidden rounded-full bg-surface-high">
        <div className="h-full rounded-full bg-primary transition-all duration-300" style={{ width: `${pct}%` }} />
      </div>

      <ul className="space-y-1.5">
        {items.map((item) => (
          <li key={item.id} className="flex items-center gap-2">
            <button
              onClick={() => toggle(item.id, !item.is_done)}
              className={cn(
                "flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors",
                item.is_done ? "border-primary bg-primary text-primary-fg" : "border-border-strong hover:border-primary",
              )}
              aria-label={item.is_done ? "Mark not done" : "Mark done"}
            >
              {item.is_done ? <Check size={11} /> : null}
            </button>
            <span className={cn("flex-1 text-[13px]", item.is_done ? "text-content-subtle line-through" : "text-content")}>
              {item.title}
            </span>
            <button
              onClick={() => remove(item.id)}
              className="text-content-subtle transition-colors hover:text-danger"
              aria-label="Remove item"
            >
              <X size={13} />
            </button>
          </li>
        ))}
      </ul>

      {items.length < MAX_ITEMS ? (
        <div className="mt-2.5 flex items-center gap-2">
          <input
            value={newItem}
            onChange={(e) => setNewItem(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && add()}
            placeholder="Add checklist item…"
            className="h-8 flex-1 rounded-md border border-border bg-surface-input px-2.5 text-[13px] text-content placeholder:text-content-subtle focus:border-primary/70 focus:outline-none"
          />
          <button
            onClick={add}
            disabled={!newItem.trim() || busy}
            className="flex h-8 items-center gap-1 rounded-md border border-border px-2.5 text-[12px] text-content-muted transition-colors hover:border-primary/60 hover:text-primary disabled:opacity-50"
          >
            <Plus size={13} /> Add
          </button>
        </div>
      ) : (
        <p className="mt-2 text-[11px] text-content-subtle">Checklist is full ({MAX_ITEMS} items).</p>
      )}
    </div>
  );
}
