// Memory and AI Knowledge context, rebuilt on the device.
//
// These blocks are fed to the model verbatim, so their format is a contract with
// the backend (memory_context_builder.py / knowledge_service.py). A silent drift
// here doesn't crash anything — it just quietly degrades every answer the phone
// gives, which is the worst kind of bug to have. The assertions below pin the
// scoring algorithm and the exact block wording.
//
//   node --test frontend/tests/ai-context.test.cjs
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const ts = require("typescript");

const compiled = ts.transpileModule(
  fs.readFileSync(path.join(__dirname, "../lib/aiContext.ts"), "utf8"),
  { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } },
).outputText;

const loaded = { exports: {} };
new Function("require", "module", "exports", compiled)(require, loaded, loaded.exports);
const { tokens, scoreChunk, searchChunks, buildMemoryBlock, buildKnowledgeBlock } = loaded.exports;

test("tokens matches the backend regex: 3+ chars, lowercased, unique", () => {
  // Backend: re.compile(r"[A-Za-z0-9_\-]{3,}")
  // The character class includes "-", so a hyphenated date is ONE token.
  assert.deepEqual([...tokens("Pay the RENT on 2026-08-20, ok?")].sort(), [
    "2026-08-20", "pay", "rent", "the",
  ].sort());
  assert.deepEqual([...tokens("a an of")], [], "words under 3 chars are dropped");
  assert.deepEqual([...tokens("Rent rent RENT")], ["rent"], "case-folded and de-duplicated");
});

test("chunk score is overlap plus a phrase bonus, normalised by query size", () => {
  const q = "rent payment";
  const qt = tokens(q);            // {rent, payment} → size 2
  // Both tokens present AND the exact phrase → (2 + 2) / 2
  assert.equal(scoreChunk(qt, q, "The rent payment is due"), 2);
  // Both tokens, no contiguous phrase → 2 / 2
  assert.equal(scoreChunk(qt, q, "payment for the rent"), 1);
  // One token → 1 / 2
  assert.equal(scoreChunk(qt, q, "rent is due"), 0.5);
  assert.equal(scoreChunk(qt, q, "nothing relevant here"), 0);
  assert.equal(scoreChunk(new Set(), "", "anything"), 0, "an empty query scores nothing");
});

test("searchChunks ranks by score and drops non-matching chunks", () => {
  const chunks = [
    { content: "unrelated filler", chunk_index: 0, document_title: "D", document_filename: "d.md" },
    { content: "rent is due", chunk_index: 1, document_title: "D", document_filename: "d.md" },
    { content: "the rent payment is due", chunk_index: 2, document_title: "D", document_filename: "d.md" },
  ];
  const hits = searchChunks(chunks, "rent payment");
  assert.equal(hits.length, 2, "zero-score chunks are excluded");
  assert.equal(hits[0].chunk_index, 2, "the phrase match ranks first");
  assert.equal(hits[1].chunk_index, 1);
  assert.deepEqual(searchChunks(chunks, "   "), [], "a blank query retrieves nothing");
});

test("the knowledge block matches the backend's wording exactly", () => {
  const block = buildKnowledgeBlock([
    { content: "Rent is 2,000,000 IDR.", chunk_index: 3, document_title: "Budget", document_filename: "budget.md", score: 2 },
  ]);
  assert.equal(
    block,
    // Note the em dash — copied from knowledge_service.retrieve_context.
    "[AI Knowledge — retrieved document context]\n" +
      "Source: Budget (budget.md) chunk 3\n" +
      "Rent is 2,000,000 IDR.\n" +
      "[End of AI Knowledge]",
  );
  assert.equal(buildKnowledgeBlock([]), null, "no hits means no block, not an empty one");
});

test("chunk text is truncated to the backend's 1400-char cap", () => {
  const block = buildKnowledgeBlock([
    { content: "x".repeat(2000), chunk_index: 0, document_title: "T", document_filename: "t.md", score: 1 },
  ]);
  assert.ok(block.includes("x".repeat(1400)));
  assert.ok(!block.includes("x".repeat(1401)));
});

test("the memory block groups by category and matches the backend's wording", () => {
  const block = buildMemoryBlock(
    [
      { category: "Profile", title: "Name", content: "User is Joshua." },
      { category: "Preferences", title: "Language", content: "Prefers Bahasa Indonesia." },
      { category: "Profile", title: "City", content: "Lives in Jakarta." },
    ],
    "what is my name",
  );
  assert.equal(
    block,
    "[AI Memory - user context, use when relevant]\n" +
      "Profile:\n" +
      "  - User is Joshua.\n" +
      "  - Lives in Jakarta.\n" +
      "Preferences:\n" +
      "  - Prefers Bahasa Indonesia.\n" +
      "[End of memory context]",
  );
  assert.equal(buildMemoryBlock([], "anything"), null);
});

test("memory ranking prefers token overlap and the always-include categories", () => {
  const memories = [
    { category: "Misc", title: "z", content: "completely unrelated trivia" },
    { category: "Misc", title: "rent", content: "monthly rent is due on the fifth" },
    { category: "Profile", title: "name", content: "user is Joshua" },
  ];
  const block = buildMemoryBlock(memories, "when is rent due");
  const lines = block.split("\n");
  // Profile carries a +1.25 always-include bonus, so it heads the block; the
  // rent memory still beats the unrelated one on overlap.
  assert.equal(lines[1], "Profile:");
  assert.ok(block.indexOf("monthly rent is due") < block.indexOf("completely unrelated"));
});

test("memory selection and block size stay inside the backend's caps", () => {
  // MAX_SELECTED_MEMORIES = 12, MAX_CONTENT_PER_MEMORY = 300, MAX_BLOCK_CHARS = 3000.
  const many = Array.from({ length: 40 }, (_, i) => ({
    category: `Cat${i}`,
    title: `t${i}`,
    content: "y".repeat(500),
  }));
  const block = buildMemoryBlock(many, "anything");
  const bullets = block.split("\n").filter((l) => l.startsWith("  - "));
  assert.ok(bullets.length <= 12, `selected ${bullets.length}, cap is 12`);
  assert.ok(bullets.every((l) => l.length <= 4 + 300), "each memory is truncated to 300 chars");
  assert.ok(block.includes("[Memory truncated to fit context limit]"), "oversized blocks say so");
});
