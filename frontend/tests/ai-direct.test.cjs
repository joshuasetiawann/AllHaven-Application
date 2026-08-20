// Direct-from-device provider calls: three different wire shapes, each easy to
// get subtly wrong in a way that only fails on a real phone against a real key.
// These assert the request we build and the reply we parse, with fetch stubbed.
//
//   node --test frontend/tests/ai-direct.test.cjs
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const ts = require("typescript");

const source = fs.readFileSync(path.join(__dirname, "../lib/aiDirect.ts"), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;

// Load with an in-memory credential store standing in for Android Keystore.
function load(keys = {}) {
  const store = { ...keys };
  const loaded = { exports: {} };
  const localRequire = (id) => {
    if (id === "@/lib/credentialStorage") {
      return {
        credentialStorage: {
          getItem: async (k) => (k in store ? store[k] : null),
          setItem: async (k, v) => { store[k] = v; },
          removeItem: async (k) => { delete store[k]; },
        },
      };
    }
    return require(id);
  };
  new Function("require", "module", "exports", compiled)(localRequire, loaded, loaded.exports);
  return { api: loaded.exports, store };
}

// Capture the single request the module makes, and reply with `body`.
function stubFetch(body, { ok = true, status = 200 } = {}) {
  const calls = [];
  global.fetch = async (url, init) => {
    calls.push({ url, init, json: init.body ? JSON.parse(init.body) : null });
    return {
      ok,
      status,
      json: async () => body,
      text: async () => JSON.stringify(body),
    };
  };
  return calls;
}

const PNG = "data:image/png;base64,AAAB";

test("OpenAI-compatible providers share one shape and differ only by base URL", async (t) => {
  const previous = global.fetch;
  t.after(() => { global.fetch = previous; });

  for (const [id, host] of [
    ["openai", "https://api.openai.com/v1/chat/completions"],
    ["grok", "https://api.x.ai/v1/chat/completions"],
    ["deepseek", "https://api.deepseek.com/v1/chat/completions"],
  ]) {
    const { api } = load({ [`ai_key_${id}`]: "sk-test" });
    const calls = stubFetch({ choices: [{ message: { content: "  hi  " } }] });
    const reply = await api.directChat(id, [{ role: "user", content: "yo" }]);

    assert.equal(reply.text, "hi", `${id} should trim the reply`);
    assert.equal(calls[0].url, host);
    assert.equal(calls[0].init.headers.Authorization, "Bearer sk-test");
    assert.equal(calls[0].json.messages[0].content, "yo");
  }
});

test("Anthropic uses x-api-key, a top-level system field, and the browser-access header", async (t) => {
  const previous = global.fetch;
  t.after(() => { global.fetch = previous; });

  const { api } = load({ ai_key_anthropic: "sk-ant" });
  const calls = stubFetch({ content: [{ type: "thinking", text: "ignored" }, { type: "text", text: "answer" }] });
  const reply = await api.directChat(
    "anthropic",
    [{ role: "system", content: "be brief" }, { role: "user", content: "hello" }],
    { images: [PNG] },
  );

  assert.equal(reply.text, "answer", "only text blocks are joined");
  const { url, init, json } = calls[0];
  assert.equal(url, "https://api.anthropic.com/v1/messages");
  assert.equal(init.headers["x-api-key"], "sk-ant");
  assert.equal(init.headers["anthropic-version"], "2023-06-01");
  // Without this the WebView origin is rejected before reaching the model.
  assert.equal(init.headers["anthropic-dangerous-direct-browser-access"], "true");
  // system is hoisted out of messages, never left as a message role.
  assert.equal(json.system, "be brief");
  assert.ok(json.messages.every((m) => m.role !== "system"));
  // The data URL is split into media type + bare base64.
  const image = json.messages.at(-1).content.find((p) => p.type === "image");
  assert.deepEqual(image.source, { type: "base64", media_type: "image/png", data: "AAAB" });
});

test("Gemini maps assistant to model and puts system in system_instruction", async (t) => {
  const previous = global.fetch;
  t.after(() => { global.fetch = previous; });

  const { api } = load({ ai_key_gemini: "goog-key" });
  const calls = stubFetch({ candidates: [{ content: { parts: [{ text: "part1 " }, { text: "part2" }] } }] });
  const reply = await api.directChat("gemini", [
    { role: "system", content: "sys" },
    { role: "user", content: "a" },
    { role: "assistant", content: "b" },
    { role: "user", content: "c" },
  ]);

  assert.equal(reply.text, "part1 part2", "parts are concatenated");
  const { url, init, json } = calls[0];
  assert.match(url, /\/models\/gemini-1\.5-flash:generateContent$/);
  assert.equal(init.headers["x-goog-api-key"], "goog-key");
  assert.equal(json.system_instruction.parts[0].text, "sys");
  assert.deepEqual(json.contents.map((c) => c.role), ["user", "model", "user"]);
});

test("a missing key fails with an actionable message, before any network call", async (t) => {
  const previous = global.fetch;
  t.after(() => { global.fetch = previous; });

  const { api } = load(); // no keys stored
  let called = false;
  global.fetch = async () => { called = true; throw new Error("should not be reached"); };

  await assert.rejects(
    () => api.directChat("openai", [{ role: "user", content: "hi" }]),
    (err) => {
      assert.equal(err.name, "DirectChatError");
      assert.match(err.message, /No API key saved on this device for openai/);
      assert.match(err.message, /Settings/, "tells the user where to fix it");
      return true;
    },
  );
  assert.equal(called, false, "must not call the provider without a key");
});

test("provider errors surface the provider's own message, not a generic one", async (t) => {
  const previous = global.fetch;
  t.after(() => { global.fetch = previous; });

  const { api } = load({ ai_key_openai: "sk-bad" });
  stubFetch({ error: { message: "Incorrect API key provided" } }, { ok: false, status: 401 });

  await assert.rejects(
    () => api.directChat("openai", [{ role: "user", content: "hi" }]),
    (err) => {
      assert.equal(err.providerId, "openai");
      assert.match(err.message, /Incorrect API key provided/);
      return true;
    },
  );
});

test("Ollama is not offered as a direct provider", () => {
  const { api } = load();
  assert.ok(!api.supportsDirect("ollama"), "Ollama runs on the desktop — the bridge path covers it");
  assert.ok(api.supportsDirect("anthropic"));
  assert.ok(!api.directProviderIds.includes("ollama"));
});

test("configuredProviders reports only the providers holding a key", async () => {
  const { api } = load({ ai_key_openai: "a", ai_key_gemini: "b" });
  assert.deepEqual(await api.configuredProviders(), ["openai", "gemini"]);
});

// --- tool calling ----------------------------------------------------------
// Tool calls are what keep the approval queue alive without the desktop: the
// model proposes, the caller files an ai_tool_proposals row, a human approves.
// Each provider reports them differently, and a shape we fail to parse is an
// action silently dropped — the model "did" something that never happened.

const TOOLS = [{
  name: "create_task",
  description: "Propose a task.",
  parameters: { type: "object", properties: { title: { type: "string" } }, required: ["title"] },
}];

test("OpenAI tool calls: declared as functions, parsed from JSON-string arguments", async (t) => {
  const previous = global.fetch;
  t.after(() => { global.fetch = previous; });

  const { api } = load({ ai_key_openai: "sk" });
  const calls = stubFetch({
    choices: [{ message: { content: null, tool_calls: [
      { function: { name: "create_task", arguments: '{"title":"Pay rent"}' } },
    ] } }],
  });
  const reply = await api.directChat("openai", [{ role: "user", content: "remind me" }], { tools: TOOLS });

  assert.equal(calls[0].json.tools[0].type, "function");
  assert.equal(calls[0].json.tools[0].function.name, "create_task");
  // Arguments arrive as a JSON *string* here and must be parsed, not passed through.
  assert.deepEqual(reply.toolCalls, [{ name: "create_task", input: { title: "Pay rent" } }]);
  assert.equal(reply.text, "", "a tool-only turn has no text, and that's valid");
});

test("Anthropic tool calls: input_schema out, tool_use blocks back", async (t) => {
  const previous = global.fetch;
  t.after(() => { global.fetch = previous; });

  const { api } = load({ ai_key_anthropic: "sk-ant" });
  const calls = stubFetch({
    content: [
      { type: "text", text: "Filing that." },
      { type: "tool_use", name: "create_task", input: { title: "Pay rent" } },
    ],
  });
  const reply = await api.directChat("anthropic", [{ role: "user", content: "remind me" }], { tools: TOOLS });

  assert.equal(calls[0].json.tools[0].name, "create_task");
  assert.ok(calls[0].json.tools[0].input_schema, "Anthropic names the field input_schema");
  assert.equal(reply.text, "Filing that.");
  assert.deepEqual(reply.toolCalls, [{ name: "create_task", input: { title: "Pay rent" } }]);
});

test("Gemini tool calls: function_declarations out, functionCall parts back", async (t) => {
  const previous = global.fetch;
  t.after(() => { global.fetch = previous; });

  const { api } = load({ ai_key_gemini: "goog" });
  const calls = stubFetch({
    candidates: [{ content: { parts: [{ functionCall: { name: "create_task", args: { title: "Pay rent" } } }] } }],
  });
  const reply = await api.directChat("gemini", [{ role: "user", content: "remind me" }], { tools: TOOLS });

  assert.equal(calls[0].json.tools[0].function_declarations[0].name, "create_task");
  assert.deepEqual(reply.toolCalls, [{ name: "create_task", input: { title: "Pay rent" } }]);
});

test("a turn that only proposes an action is not treated as an empty response", async (t) => {
  const previous = global.fetch;
  t.after(() => { global.fetch = previous; });

  const { api } = load({ ai_key_openai: "sk" });
  stubFetch({ choices: [{ message: { content: null, tool_calls: [
    { function: { name: "create_task", arguments: '{"title":"x"}' } },
  ] } }] });

  const reply = await api.directChat("openai", [{ role: "user", content: "hi" }], { tools: TOOLS });
  assert.equal(reply.toolCalls.length, 1);
});

test("unparseable tool arguments yield an empty input, never a fabricated one", async (t) => {
  const previous = global.fetch;
  t.after(() => { global.fetch = previous; });

  const { api } = load({ ai_key_openai: "sk" });
  stubFetch({ choices: [{ message: { content: "done", tool_calls: [
    { function: { name: "create_task", arguments: "{not json" } },
  ] } }] });

  const reply = await api.directChat("openai", [{ role: "user", content: "hi" }], { tools: TOOLS });
  assert.deepEqual(reply.toolCalls, [{ name: "create_task", input: {} }]);
});

test("no tools passed means no tools field — providers reject empty arrays", async (t) => {
  const previous = global.fetch;
  t.after(() => { global.fetch = previous; });

  const { api } = load({ ai_key_openai: "sk" });
  const calls = stubFetch({ choices: [{ message: { content: "hi" } }] });
  await api.directChat("openai", [{ role: "user", content: "hi" }]);
  assert.ok(!("tools" in calls[0].json));
});
