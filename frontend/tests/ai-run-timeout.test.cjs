// AI runs (parallel fan-out, debate rounds, reasoning council) take as long as
// they take. The generic 20s (6s on mobile) request guard used to abort them
// mid-thought, which killed the "thinking…" spinner and surfaced a false
// timeout error while the backend kept working.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const ts = require("typescript");

const apiRestJavaScript = ts.transpileModule(
  fs.readFileSync(path.join(__dirname, "../lib/apiRest.ts"), "utf8"),
  { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } },
).outputText;

// Load apiRest with its browser/auth deps stubbed and fetch replaced by a call
// that never settles, so only the abort timer can end the request.
function loadApiRest() {
  const loaded = { exports: {} };
  const localRequire = (id) => {
    if (id === "@/lib/auth") return { clearAuth() {} };
    if (id === "@/lib/backendUrl") return { getApiBaseUrl: () => "http://localhost:8000" };
    if (id === "@/lib/mobileAuth") {
      return {
        BEARER_MODE: true, // tightest generic timeout (6s) — worst case for AI runs
        clearBearerToken: async () => {},
        ensureBearerHydrated: async () => {},
        getBearerToken: () => "t",
        setBearerToken: async () => {},
      };
    }
    return require(id);
  };
  new Function("require", "module", "exports", apiRestJavaScript)(localRequire, loaded, loaded.exports);
  return loaded.exports;
}

// Fires every `calls` at once against a fetch that never settles, waits past the
// generic guard, then reports which ones the abort timer killed.
async function abortedAfter(calls, ms) {
  const previousFetch = global.fetch;
  const signals = {};
  const releases = [];
  global.fetch = (url, init) => {
    signals[url] = init.signal;
    return new Promise((_res, rej) => releases.push(() => rej(new Error("released"))));
  };
  try {
    const done = Promise.all(Object.values(calls).map((c) => c().catch(() => {})));
    await new Promise((r) => setTimeout(r, ms));
    const aborted = Object.entries(signals).filter(([, s]) => s.aborted).map(([url]) => url);
    // Settle the requests so their pending abort timers are cleared, otherwise a
    // 5-minute timer would keep the test process alive.
    releases.forEach((r) => r());
    await done;
    assert.equal(Object.keys(signals).length, Object.keys(calls).length, "a call never reached fetch");
    return aborted;
  } finally {
    global.fetch = previousFetch;
  }
}

test("AI run endpoints are never aborted on a timer", async () => {
  const { aiApi } = loadApiRest();
  // BEARER_MODE puts the generic guard at 6s — wait past it, so this test fails
  // if any AI endpoint falls back to the default timeout.
  const aborted = await abortedAfter({
    chat: () => aiApi.chat("hi"),
    multiChat: () => aiApi.multiChat("hi", ["a"]),
    debateChat: () => aiApi.debateChat("hi", ["a", "b"], undefined, 3),
    reasonChat: () => aiApi.reasonChat("hi", ["a"]),
  }, 6500);
  assert.deepEqual(aborted, [], "AI runs must not be aborted by the generic timeout");
});

test("non-AI endpoints are still aborted by the generic timeout", async () => {
  const { aiApi } = loadApiRest();
  const aborted = await abortedAfter({ listSessions: () => aiApi.listSessions() }, 6500);
  assert.equal(aborted.length, 1, "ordinary requests must still fail fast");
});

// With no clock on AI runs, the Stop button is the only way out of a request
// that hangs — and pressing it must not look like a server failure.
test("Stop cancels an in-flight AI run and reports CANCELLED", async () => {
  const { aiApi } = loadApiRest();
  const previousFetch = global.fetch;
  global.fetch = (_url, init) => new Promise((_res, rej) => {
    init.signal.addEventListener("abort", () => rej(new DOMException("aborted", "AbortError")), { once: true });
  });
  try {
    for (const [name, call] of Object.entries({
      multiChat: (s) => aiApi.multiChat("hi", ["a"], undefined, undefined, "balance", "general", undefined, s),
      debateChat: (s) => aiApi.debateChat("hi", ["a"], undefined, 2, undefined, "balance", "general", undefined, s),
      reasonChat: (s) => aiApi.reasonChat("hi", ["a"], undefined, "balance", undefined, "general", undefined, s),
    })) {
      const stop = new AbortController();
      const pending = call(stop.signal).then(() => null, (e) => e);
      await new Promise((r) => setTimeout(r, 10));
      stop.abort();
      const err = await pending;
      assert.ok(err, `${name} should reject when stopped`);
      assert.equal(err.code, "CANCELLED", `${name} must report CANCELLED, not a timeout`);
    }
  } finally {
    global.fetch = previousFetch;
  }
});
