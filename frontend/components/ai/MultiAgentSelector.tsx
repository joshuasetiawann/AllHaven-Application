"use client";

import { useMemo, useState } from "react";
import { Eye, Plus, X } from "lucide-react";
import { StatusDot } from "@/components/ui/StatusDot";
import { cn } from "@/lib/format";
import type { AiProvider } from "@/types";

export const MAX_AGENTS = 7;

// One selectable agent: a provider model slot. Slot 1's ref is the plain
// provider id (backward compatible); slot 2's ref is "<provider>#2".
interface AgentOption {
  ref: string;
  label: string;
  role: string;
  model: string;
  provider: AiProvider;
}

// Slot 1 is always offered; slot 2 only once it is configured and enabled.
// Providers without slot data fall back to a single slot-1 option.
function buildOptions(providers: AiProvider[]): AgentOption[] {
  const options: AgentOption[] = [];
  for (const p of providers) {
    const slots = p.model_slots?.length
      ? p.model_slots
      : [{ slot: 1, ref: p.id, model: p.default_model ?? "", role: "", enabled: true, configured: true }];
    for (const s of slots) {
      if (s.slot !== 1 && !(s.configured && s.enabled)) continue;
      options.push({
        ref: s.ref,
        label: `${p.name}${s.slot === 2 ? " · Slot 2" : ""}`,
        role: s.role,
        model: s.model,
        provider: p,
      });
    }
  }
  return options;
}

/**
 * Select 1–7 AI agents (provider model slots) to run concurrently. Shows selected
 * agents as chips and an "Add agent" menu of the remaining slots; adding is
 * disabled at 7. Selected values are slot refs (slot 1 = the plain provider id).
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

  const options = useMemo(() => buildOptions(providers), [providers]);
  const byRef = (ref: string) => options.find((o) => o.ref === ref);
  // Stale refs (e.g. a slot unconfigured after selection) still resolve to a provider chip.
  const providerOf = (ref: string) => byRef(ref)?.provider ?? providers.find((p) => p.id === ref.split("#")[0]);
  const available = options.filter((o) => !selected.includes(o.ref));
  const atMax = selected.length >= MAX_AGENTS;

  const add = (ref: string) => {
    if (selected.includes(ref)) return;
    if (atMax) {
      setWarn(`Maximum ${MAX_AGENTS} agents per run.`);
      return;
    }
    setWarn(null);
    onChange([...selected, ref]);
    setOpen(false);
  };

  const remove = (ref: string) => {
    setWarn(null);
    onChange(selected.filter((s) => s !== ref));
  };

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-wrap items-center gap-2">
        {selected.map((ref) => {
          const o = byRef(ref);
          const p = providerOf(ref);
          return (
            <span
              key={ref}
              className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-input py-1 pl-2.5 pr-1.5 text-[12.5px] text-content"
            >
              <StatusDot status={p?.status ?? "not_configured"} />
              <span className="max-w-[140px] truncate">{o?.label ?? p?.name ?? ref}</span>
              {o?.role ? <span className="max-w-[110px] truncate text-[10px] text-content-subtle">{o.role}</span> : null}
              {p?.capabilities?.image ? <Eye size={11} className="text-content-subtle" aria-label="Supports images" /> : null}
              <span className="text-[10px] uppercase text-content-subtle">{p?.external ? "ext" : "local"}</span>
              <button
                type="button"
                onClick={() => remove(ref)}
                aria-label={`Remove ${o?.label ?? p?.name ?? ref}`}
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
                <p className="px-2 py-2 text-[12.5px] text-content-muted">No more agents.</p>
              ) : (
                available.map((o) => (
                  <button
                    key={o.ref}
                    type="button"
                    onClick={() => add(o.ref)}
                    className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-[13px] text-content hover:bg-surface-raised/70"
                  >
                    <StatusDot status={o.provider.status} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate">{o.label}</span>
                      {o.role ? <span className="block truncate text-[10.5px] text-content-subtle">{o.role}</span> : null}
                    </span>
                    {o.provider.capabilities?.image ? <Eye size={11} className="shrink-0 text-content-subtle" aria-label="Supports images" /> : null}
                    <span className="shrink-0 text-[10px] uppercase text-content-subtle">{o.provider.external ? "ext" : "local"}</span>
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
