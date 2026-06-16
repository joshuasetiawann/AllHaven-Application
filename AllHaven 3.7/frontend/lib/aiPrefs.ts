// Persisted AI chat selection — so the user never has to re-pick their model,
// agents, or mode when navigating between pages or refreshing the browser.
//
// Backend chat settings (default mode, debate-flow visibility) remain the
// workspace source of truth; this stores the *user's last-used selection*
// locally and restores it on load. No secrets — only ids and enum-like prefs.

import { defineStore, type Store } from "@/lib/storage";
import { DEFAULT_SECTION_KEY } from "@/lib/sections";
import type { AiProvider, ThinkingMode } from "@/types";

export type ChatModePref = "parallel" | "debate" | "reason";

export interface AiSelectionPrefs {
  /** Agent slot refs (slot 1 = plain provider id, slot 2 = "<id>#2"). */
  selected_agent_ids: string[];
  chat_mode: ChatModePref;
  thinking: ThinkingMode;
  rounds: number;
  /** Active chat "section" whose local memory is in use. */
  section_key: string;
}

export const DEFAULT_AI_PREFS: AiSelectionPrefs = {
  selected_agent_ids: [],
  chat_mode: "parallel",
  thinking: "balance",
  rounds: 2,
  section_key: DEFAULT_SECTION_KEY,
};

const VALID_MODES: ChatModePref[] = ["parallel", "debate", "reason"];
const VALID_THINKING: ThinkingMode[] = ["fast", "balance", "thinking", "deep"];

const store: Store<AiSelectionPrefs> = defineStore<AiSelectionPrefs>(
  "ai-selection",
  1,
  DEFAULT_AI_PREFS,
  (raw) => {
    const r = (raw ?? {}) as Partial<AiSelectionPrefs>;
    return {
      selected_agent_ids: Array.isArray(r.selected_agent_ids)
        ? r.selected_agent_ids.filter((x): x is string => typeof x === "string")
        : [],
      chat_mode: VALID_MODES.includes(r.chat_mode as ChatModePref) ? (r.chat_mode as ChatModePref) : "parallel",
      thinking: VALID_THINKING.includes(r.thinking as ThinkingMode) ? (r.thinking as ThinkingMode) : "balance",
      rounds: r.rounds === 3 ? 3 : 2,
      section_key: typeof r.section_key === "string" ? r.section_key : DEFAULT_SECTION_KEY,
    };
  },
);

export function loadAiPrefs(): AiSelectionPrefs {
  return store.get();
}

/** Whether the user has any saved selection yet (vs. first-ever load). */
export function aiPrefsExist(): boolean {
  return store.exists();
}

export function saveAiPrefs(patch: Partial<AiSelectionPrefs>): AiSelectionPrefs {
  return store.update((cur) => ({ ...cur, ...patch }));
}

// --- availability resolution ------------------------------------------------

/** Every selectable agent ref currently offered by the providers list. */
export function availableAgentRefs(providers: AiProvider[]): Set<string> {
  const refs = new Set<string>();
  for (const p of providers) {
    const slots = p.model_slots?.length
      ? p.model_slots
      : [{ slot: 1, ref: p.id, configured: true, enabled: true } as { slot: number; ref: string; configured: boolean; enabled: boolean }];
    for (const s of slots) {
      if (s.slot !== 1 && !(s.configured && s.enabled)) continue;
      refs.add(s.ref);
    }
  }
  return refs;
}

export type SelectionStatus =
  | { kind: "ok"; selected: string[] }
  | { kind: "fallback"; selected: string[]; dropped: string[]; message: string }
  | { kind: "none"; selected: string[]; message: string };

/**
 * Reconcile a persisted selection against the providers actually available.
 * - Drops refs that no longer exist (e.g. a provider was disabled) and warns.
 * - Falls back to the first local provider (Ollama) when nothing valid remains.
 * - Reports when no provider is configured at all.
 */
export function resolveSelection(persisted: string[], providers: AiProvider[]): SelectionStatus {
  if (providers.length === 0) {
    return { kind: "none", selected: [], message: "Configure an AI provider first." };
  }
  const available = availableAgentRefs(providers);
  const kept = persisted.filter((ref) => available.has(ref));
  const dropped = persisted.filter((ref) => !available.has(ref));

  if (kept.length > 0) {
    if (dropped.length > 0) {
      return {
        kind: "fallback",
        selected: kept,
        dropped,
        message: `Some saved models are unavailable and were removed. Choose another model if needed.`,
      };
    }
    return { kind: "ok", selected: kept };
  }

  // Nothing valid kept — pick a sensible default (prefer local Ollama).
  const fallback = providers.find((p) => p.id === "ollama") ?? providers[0];
  const fallbackRef = fallback?.id;
  if (!fallbackRef) {
    return { kind: "none", selected: [], message: "Configure an AI provider first." };
  }
  if (persisted.length > 0) {
    return {
      kind: "fallback",
      selected: [fallbackRef],
      dropped: persisted,
      message: "Your saved model is unavailable — switched to a default. Choose another model if needed.",
    };
  }
  return { kind: "ok", selected: [fallbackRef] };
}
