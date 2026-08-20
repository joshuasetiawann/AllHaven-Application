// frontend/lib/aiContext.ts — memory + AI Knowledge context, built on-device.
//
// Both blocks normally come from the backend. They don't have to: memories and
// knowledge chunks are ordinary rows in the same Supabase database the phone
// already reads, and the backend's retrieval is plain keyword scoring — no
// embeddings, no pgvector. So the phone can build the identical context itself
// and keep memory and knowledge working with the desktop off.
//
// These functions are deliberately pure (rows in, string out) so they can be
// tested against the backend's exact output format. The Supabase reads live in
// apiSupabase.ts. Constants and formats mirror
// backend/app/services/memory_context_builder.py and knowledge_service.py —
// when either changes there, change it here.

// Backend: _WORD_RE = re.compile(r"[A-Za-z0-9_\-]{3,}")
const WORD_RE = /[A-Za-z0-9_-]{3,}/g;

/** Unique lowercased words of 3+ chars — the backend's `_tokens`. */
export function tokens(text: string): Set<string> {
  return new Set((text || "").toLowerCase().match(WORD_RE) ?? []);
}

const overlapCount = (a: Set<string>, b: Set<string>) => {
  let n = 0;
  for (const t of a) if (b.has(t)) n += 1;
  return n;
};

// --- Memory ----------------------------------------------------------------
const MAX_CONTENT_PER_MEMORY = 300;
const MAX_BLOCK_CHARS = 3000;
const MAX_SELECTED_MEMORIES = 12;
const ALWAYS_INCLUDE = new Set(["Profile", "Preferences", "Writing style"]);

export type MemoryRow = {
  category: string;
  title: string;
  content: string;
  relevance_score?: number | null;
  last_used_at?: string | null;
};

/** Backend `_ranked_relevant` + `_format_block`, same weights and wording. */
export function buildMemoryBlock(memories: MemoryRow[], message: string, sectionKey?: string): string | null {
  if (!memories.length) return null;
  const msgTokens = tokens(message);
  const section = (sectionKey || "").toLowerCase();

  const score = (m: MemoryRow): number => {
    const text = tokens(`${m.title} ${m.content} ${m.category}`);
    let s = Number(m.relevance_score ?? 0);
    s += overlapCount(msgTokens, text) * 0.25;
    if (ALWAYS_INCLUDE.has(m.category)) s += 1.25;
    if (section && (m.content || "").toLowerCase().includes(section)) s += 0.5;
    if (m.last_used_at) s += 0.15;
    return s;
  };

  const selected = [...memories].sort((a, b) => score(b) - score(a)).slice(0, MAX_SELECTED_MEMORIES);
  if (!selected.length) return null;

  const byCategory = new Map<string, string[]>();
  for (const m of selected) {
    const list = byCategory.get(m.category) ?? [];
    list.push((m.content || "").slice(0, MAX_CONTENT_PER_MEMORY));
    byCategory.set(m.category, list);
  }

  const lines = ["[AI Memory - user context, use when relevant]"];
  for (const [cat, contents] of byCategory) {
    lines.push(`${cat}:`);
    for (const c of contents) lines.push(`  - ${c}`);
  }
  lines.push("[End of memory context]");

  const block = lines.join("\n");
  return block.length > MAX_BLOCK_CHARS
    ? `${block.slice(0, MAX_BLOCK_CHARS)}\n[Memory truncated to fit context limit]`
    : block;
}

// --- AI Knowledge ----------------------------------------------------------
const MAX_CHUNK_CHARS = 1400;

export type KnowledgeChunkRow = {
  content: string;
  chunk_index: number;
  document_title: string;
  document_filename: string;
};

export type KnowledgeHit = KnowledgeChunkRow & { score: number };

/** Backend `_score`: token overlap plus a phrase bonus, normalised by query size. */
export function scoreChunk(queryTokens: Set<string>, query: string, content: string): number {
  if (queryTokens.size === 0) return 0;
  const lower = (content || "").toLowerCase();
  const overlap = overlapCount(queryTokens, tokens(lower));
  const phraseBonus = lower.includes(query.toLowerCase()) ? 2 : 0;
  return (overlap + phraseBonus) / Math.max(1, queryTokens.size);
}

/** Backend `search_knowledge` — candidates in, ranked hits out. Zero-score chunks are dropped. */
export function searchChunks(chunks: KnowledgeChunkRow[], query: string, limit = 3): KnowledgeHit[] {
  const q = (query || "").trim();
  if (!q) return [];
  const qTokens = tokens(q);
  return chunks
    .map((c) => ({ ...c, score: scoreChunk(qTokens, q, c.content) }))
    .filter((c) => c.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, Math.max(1, Math.min(limit, 10)));
}

/** Backend `retrieve_context` block, byte-for-byte (note the em dash in the header). */
export function buildKnowledgeBlock(hits: KnowledgeHit[]): string | null {
  if (!hits.length) return null;
  const lines = ["[AI Knowledge — retrieved document context]"];
  for (const h of hits) {
    lines.push(`Source: ${h.document_title} (${h.document_filename}) chunk ${h.chunk_index}`);
    lines.push(String(h.content).slice(0, MAX_CHUNK_CHARS));
  }
  lines.push("[End of AI Knowledge]");
  return lines.join("\n");
}
