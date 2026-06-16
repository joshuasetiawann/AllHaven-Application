"use client";

import { useMemo, useState } from "react";
import { Bot, Check, Eye, Plus, Search, X } from "lucide-react";
import { StatusDot } from "@/components/ui/StatusDot";
import { cn } from "@/lib/format";
import type { AiProvider, ModelSlot } from "@/types";

export const MAX_AGENTS = 10;

// One selectable agent: a provider model slot. Slot 1's ref is the plain
// provider id (backward compatible); slot 2's ref is "<provider>#2".
interface AgentOption {
  ref: string;
  label: string;
  role: string;
  model: string;
  slot: ModelSlot["slot"];
  provider: AiProvider;
}

function providerBaseName(provider: AiProvider) {
  if (provider.id.startsWith("openrouter_")) return provider.name;
  const names: Record<string, string> = {
    ollama: "Ollama",
    openai: "GPT",
    anthropic: "Claude",
    gemini: "Gemini",
    grok: "Grok",
    blackbox: "Blackbox",
    cursor: "Cursor",
    deepseek: "DeepSeek",
    qwen: "Qwen",
  };
  return names[provider.id] ?? provider.name.replace(/\s+Agent$/i, "");
}

function slotLabel(provider: AiProvider, slot: ModelSlot) {
  if (provider.id.startsWith("openrouter_")) return provider.name;
  return `${providerBaseName(provider)} ${slot.slot}`;
}

function optionMatches(option: AgentOption, query: string) {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return [option.label, option.role, option.model, option.provider.name, option.provider.purpose]
    .some((value) => (value || "").toLowerCase().includes(q));
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
        label: slotLabel(p, s),
        role: s.role,
        model: s.model,
        slot: s.slot,
        provider: p,
      });
    }
  }
  return options;
}

/**
 * Select 1-10 AI agents (provider model slots) to run concurrently. Shows selected
 * agents as chips and an "Add agent" menu of the remaining slots; adding is
 * disabled at 10. Selected values are slot refs (slot 1 = the plain provider id).
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
  const [query, setQuery] = useState("");

  const options = useMemo(() => buildOptions(providers), [providers]);
  const byRef = (ref: string) => options.find((o) => o.ref === ref);
  // Stale refs (e.g. a slot unconfigured after selection) still resolve to a provider chip.
  const providerOf = (ref: string) => byRef(ref)?.provider ?? providers.find((p) => p.id === ref.split("#")[0]);
  const available = options.filter((o) => !selected.includes(o.ref));
  const filteredAvailable = available.filter((o) => optionMatches(o, query));
  const openRouterOptions = filteredAvailable.filter((o) => o.provider.id.startsWith("openrouter_"));
  const directOptions = filteredAvailable.filter((o) => !o.provider.id.startsWith("openrouter_"));
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
    setQuery("");
  };

  const remove = (ref: string) => {
    setWarn(null);
    onChange(selected.filter((s) => s !== ref));
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        {selected.map((ref) => {
          const o = byRef(ref);
          const p = providerOf(ref);
          return (
            <span
              key={ref}
              className="inline-flex min-h-8 items-center gap-1.5 rounded-full border border-border bg-surface-input py-1 pl-2.5 pr-1.5 text-[12.5px] text-content"
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
            <div className="absolute left-0 top-9 z-40 w-[min(340px,calc(100vw-2rem))] animate-scale-in rounded-xl border border-border bg-surface p-2 shadow-glow">
              <div className="relative mb-2">
                <Search size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-content-subtle" />
                <input
                  autoFocus
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search GPT, Gemini, Cursor, DeepSeek, Qwen..."
                  className="h-9 w-full rounded-lg border border-border bg-surface-input pl-8 pr-3 text-[13px] text-content outline-none transition-colors placeholder:text-content-subtle focus:border-primary/60"
                />
              </div>
              {available.length === 0 ? (
                <p className="px-2 py-2 text-[12.5px] text-content-muted">No more agents.</p>
              ) : filteredAvailable.length === 0 ? (
                <p className="px-2 py-2 text-[12.5px] text-content-muted">No agent matches this search.</p>
              ) : (
                <div className="max-h-80 overflow-y-auto pr-1">
                  <OptionGroup title="Direct model agents" options={directOptions} onAdd={add} />
                  <OptionGroup title="OpenRouter agents" options={openRouterOptions} onAdd={add} />
                </div>
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

function OptionGroup({
  title,
  options,
  onAdd,
}: {
  title: string;
  options: AgentOption[];
  onAdd: (ref: string) => void;
}) {
  if (!options.length) return null;
  return (
    <div className="py-1">
      <p className="px-2 pb-1 pt-1 text-[10px] uppercase tracking-[0.18em] text-content-subtle">{title}</p>
      <div className="space-y-1">
        {options.map((o) => (
          <button
            key={o.ref}
            type="button"
            onClick={() => onAdd(o.ref)}
            className="group flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-[13px] text-content hover:bg-surface-raised/70"
          >
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-input text-primary">
              <Bot size={14} />
            </span>
            <span className="min-w-0 flex-1">
              <span className="flex items-center gap-1.5">
                <StatusDot status={o.provider.status} />
                <span className="truncate font-medium">{o.label}</span>
              </span>
              <span className="mt-0.5 block truncate text-[11px] text-content-subtle">
                {o.model || "No model set"}{o.role ? ` · ${o.role}` : ""}
              </span>
            </span>
            {o.provider.capabilities?.image ? <Eye size={12} className="shrink-0 text-content-subtle" aria-label="Supports images" /> : null}
            <span className="shrink-0 rounded-full border border-border px-1.5 py-0.5 text-[10px] uppercase text-content-subtle">
              {o.provider.external ? "ext" : "local"}
            </span>
            <Check size={13} className="shrink-0 text-primary opacity-0 transition-opacity group-hover:opacity-100" />
          </button>
        ))}
      </div>
    </div>
  );
}
