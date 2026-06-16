"use client";

import { useState } from "react";
import { Plus, X } from "lucide-react";
import { StatusDot } from "@/components/ui/StatusDot";
import { cn } from "@/lib/format";
import type { AiProvider } from "@/types";

export const MAX_AGENTS = 3;

/**
 * Select 1–3 AI agents to run concurrently. Shows selected agents as chips and an
 * "Add agent" menu of the remaining providers; adding is disabled at 3.
 */
export function MultiAgentSelector({
  providers,
  selected,
  onChange,
  hint = "they run at the same time.",
}: {
  providers: AiProvider[];
  selected: string[];
  onChange: (ids: string[]) => void;
  hint?: string;
}) {
  const [open, setOpen] = useState(false);
  const [warn, setWarn] = useState<string | null>(null);

  const byId = (id: string) => providers.find((p) => p.id === id);
  const available = providers.filter((p) => !selected.includes(p.id));
  const atMax = selected.length >= MAX_AGENTS;

  const add = (id: string) => {
    if (selected.includes(id)) return;
    if (atMax) {
      setWarn(`Maximum ${MAX_AGENTS} agents per run.`);
      return;
    }
    setWarn(null);
    onChange([...selected, id]);
    setOpen(false);
  };

  const remove = (id: string) => {
    setWarn(null);
    onChange(selected.filter((s) => s !== id));
  };

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-wrap items-center gap-2">
        {selected.map((id) => {
          const p = byId(id);
          return (
            <span
              key={id}
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-input py-1 pl-2.5 pr-1.5 text-[12.5px] text-content"
            >
              <StatusDot status={p?.status ?? "not_configured"} />
              <span className="max-w-[140px] truncate">{p?.name ?? id}</span>
              <span className="text-[10px] uppercase text-content-subtle">{p?.external ? "ext" : "local"}</span>
              <button
                type="button"
                onClick={() => remove(id)}
                aria-label={`Remove ${p?.name ?? id}`}
                className="ml-0.5 rounded-full p-0.5 text-content-subtle hover:bg-surface-raised hover:text-content"
              >
                <X size={13} />
              </button>
            </span>
          );
        })}

        <div className="relative">
          <button
            type="button"
            disabled={atMax || available.length === 0}
            onClick={() => setOpen((o) => !o)}
            className={cn(
              "inline-flex items-center gap-1 rounded-full border border-dashed border-border px-2.5 py-1 text-[12.5px] transition-colors",
              atMax || available.length === 0
                ? "cursor-not-allowed text-content-subtle opacity-60"
                : "text-content-muted hover:border-primary/50 hover:text-content",
            )}
          >
            <Plus size={13} /> Add agent
          </button>
          {open && !atMax ? (
            <div className="absolute left-0 top-9 z-40 max-h-72 w-60 animate-scale-in overflow-y-auto rounded-xl border border-border bg-surface p-1.5 shadow-glow">
              {available.length === 0 ? (
                <p className="px-2 py-2 text-[12.5px] text-content-muted">No more providers.</p>
              ) : (
                available.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => add(p.id)}
                    className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-[13px] text-content hover:bg-surface-raised/70"
                  >
                    <StatusDot status={p.status} />
                    <span className="flex-1 truncate">{p.name}</span>
                    <span className="text-[10px] uppercase text-content-subtle">{p.external ? "ext" : "local"}</span>
                  </button>
                ))
              )}
            </div>
          ) : null}
        </div>
      </div>

      <p className="text-[11.5px] text-content-subtle">
        {selected.length}/{MAX_AGENTS} agents selected — {hint}
        {warn ? <span className="ml-1 text-warning">{warn}</span> : null}
      </p>
    </div>
  );
}
