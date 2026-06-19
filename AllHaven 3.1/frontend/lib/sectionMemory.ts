// Per-section chat memory — small, local, human-editable context the AI can use
// to give more relevant answers within a given module (Finance, Notes, …).
//
// Stored locally only (localStorage via the storage abstraction). Never holds
// secrets: every value written is passed through `redactSecrets` first, and the
// store is namespaced so "clear all local data" wipes it. Designed so the shape
// (`SectionMemory`) can later be backed by IndexedDB or a server table without
// touching call sites.

import { defineStore, type Store } from "@/lib/storage";

export interface SectionMemory {
  id: string;
  section_key: string;
  title: string;
  summary: string;
  important_context: string[];
  updated_at: string; // ISO timestamp
}

type MemoryMap = Record<string, SectionMemory>;

const store: Store<MemoryMap> = defineStore<MemoryMap>(
  "section-memory",
  1,
  {},
  (raw) => (raw && typeof raw === "object" ? (raw as MemoryMap) : {}),
);

// --- secret redaction -------------------------------------------------------

// Mask things that look like credentials so they never land in local memory.
// Conservative on purpose — over-masking is safe, leaking is not.
const SECRET_PATTERNS: RegExp[] = [
  /\bsk-[A-Za-z0-9_-]{12,}\b/g, // OpenAI-style keys
  /\b(?:gsk|pk|rk|xoxb|xoxp|ghp|gho|github_pat)_[A-Za-z0-9_-]{8,}\b/g, // provider/GitHub tokens
  /\bAKIA[0-9A-Z]{16}\b/g, // AWS access key id
  /\bBearer\s+[A-Za-z0-9._-]{12,}\b/gi, // bearer tokens
  /\beyJ[A-Za-z0-9._-]{20,}\b/g, // JWTs
  /\b[A-Za-z0-9_-]{32,}\b/g, // long opaque tokens / api keys
];

const MASK = "•••redacted•••";

export function redactSecrets(text: string): string {
  if (!text) return text;
  let out = text;
  // Also catch "key: value" / "token=value" style assignments.
  out = out.replace(
    /\b(api[_-]?key|secret|token|password|passwd|pwd|authorization)\b\s*[:=]\s*\S+/gi,
    (_m, label: string) => `${label}: ${MASK}`,
  );
  for (const re of SECRET_PATTERNS) out = out.replace(re, MASK);
  return out;
}

function redactList(items: string[]): string[] {
  return items
    .map((s) => redactSecrets(s).trim())
    .filter((s) => s.length > 0)
    .slice(0, 12); // keep memory bounded
}

// --- id / time helpers ------------------------------------------------------

function newId(): string {
  const rnd = Math.floor(Math.random() * 1e9).toString(36);
  return `sm_${Date.now().toString(36)}${rnd}`;
}

function now(): string {
  return new Date().toISOString();
}

// --- public API -------------------------------------------------------------

export function getAllMemories(): SectionMemory[] {
  return Object.values(store.get()).sort((a, b) => b.updated_at.localeCompare(a.updated_at));
}

export function getMemory(sectionKey: string): SectionMemory | null {
  return store.get()[sectionKey] ?? null;
}

export interface MemoryPatch {
  title?: string;
  summary?: string;
  important_context?: string[];
}

/** Create or merge a section's memory (all values are redacted before save). */
export function upsertMemory(sectionKey: string, patch: MemoryPatch): SectionMemory {
  return store.update((map) => {
    const prev = map[sectionKey];
    const next: SectionMemory = {
      id: prev?.id ?? newId(),
      section_key: sectionKey,
      title: redactSecrets(patch.title ?? prev?.title ?? "").slice(0, 80),
      summary: redactSecrets(patch.summary ?? prev?.summary ?? "").slice(0, 600),
      important_context: redactList(patch.important_context ?? prev?.important_context ?? []),
      updated_at: now(),
    };
    return { ...map, [sectionKey]: next };
  })[sectionKey];
}

/** Append one important-context bullet (redacted, de-duplicated). */
export function addContext(sectionKey: string, line: string): SectionMemory | null {
  const clean = redactSecrets(line).trim();
  if (!clean) return getMemory(sectionKey);
  const prev = getMemory(sectionKey);
  const list = prev?.important_context ?? [];
  if (list.includes(clean)) return prev;
  return upsertMemory(sectionKey, { important_context: [...list, clean] });
}

export function clearSection(sectionKey: string): void {
  store.update((map) => {
    if (!(sectionKey in map)) return map;
    const next = { ...map };
    delete next[sectionKey];
    return next;
  });
}

export function clearAllMemories(): void {
  store.set({});
}

export function hasMemory(sectionKey: string): boolean {
  const m = getMemory(sectionKey);
  return Boolean(m && (m.summary || m.important_context.length || m.title));
}

/**
 * Build a compact, prependable context block for a section's prompt, or null
 * when there is nothing useful. Kept short so it never dominates the prompt.
 */
export function buildContextPreface(sectionKey: string, sectionLabel: string): string | null {
  const m = getMemory(sectionKey);
  if (!m || (!m.summary && m.important_context.length === 0)) return null;
  const lines: string[] = [`[${sectionLabel} memory — local context the user saved for this section]`];
  if (m.title) lines.push(`Topic: ${m.title}`);
  if (m.summary) lines.push(`Summary: ${m.summary}`);
  if (m.important_context.length) {
    lines.push("Important context:");
    for (const c of m.important_context) lines.push(`- ${c}`);
  }
  lines.push("[Use this only if relevant to the user's message below.]");
  return lines.join("\n");
}
