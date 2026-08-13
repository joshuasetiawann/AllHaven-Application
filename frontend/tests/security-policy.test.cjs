const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const ts = require("typescript");

const { buildContentSecurityPolicy } = require("../lib/contentSecurityPolicy");
const backendPolicy = require("../lib/backendUrlPolicy");
const {
  cookieBackendMatchesPage,
  isPrivateBridgeHostname,
  isLoopbackHostname,
  rewriteLoopbackBackendForPage,
} = backendPolicy;

const backendUrlSource = fs.readFileSync(path.join(__dirname, "../lib/backendUrl.ts"), "utf8");
const backendUrlJavaScript = ts.transpileModule(backendUrlSource, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;
const apiRestSource = fs.readFileSync(path.join(__dirname, "../lib/apiRest.ts"), "utf8");
const apiRestJavaScript = ts.transpileModule(apiRestSource, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;

function withBackendUrl(
  {
    bearer = false,
    env,
    stored = "",
    page = { protocol: "http:", hostname: "localhost", port: "3000" },
  },
  assertion,
) {
  const previousWindow = global.window;
  const previousEnv = process.env.NEXT_PUBLIC_API_BASE_URL;
  let saved = stored;
  global.window = {
    location: page,
    localStorage: {
      getItem: () => saved,
      setItem: (_key, value) => { saved = value; },
      removeItem: () => { saved = ""; },
    },
  };
  if (env === undefined) delete process.env.NEXT_PUBLIC_API_BASE_URL;
  else process.env.NEXT_PUBLIC_API_BASE_URL = env;

  const loaded = { exports: {} };
  const localRequire = (id) => {
    if (id === "@/lib/mobileAuth") return { BEARER_MODE: bearer };
    if (id === "@/lib/backendUrlPolicy") return backendPolicy;
    return require(id);
  };

  try {
    new Function("require", "module", "exports", backendUrlJavaScript)(
      localRequire,
      loaded,
      loaded.exports,
    );
    assertion(loaded.exports, () => saved);
  } finally {
    global.window = previousWindow;
    if (previousEnv === undefined) delete process.env.NEXT_PUBLIC_API_BASE_URL;
    else process.env.NEXT_PUBLIC_API_BASE_URL = previousEnv;
  }
}

function loadApiRest({ baseUrl = "", bearer = true, token = "secret-bearer" } = {}) {
  let tokenReads = 0;
  let tokenClears = 0;
  const loaded = { exports: {} };
  const localRequire = (id) => {
    if (id === "@/lib/auth") return { clearAuth() {} };
    if (id === "@/lib/backendUrl") return { getApiBaseUrl: () => baseUrl };
    if (id === "@/lib/mobileAuth") {
      return {
        BEARER_MODE: bearer,
        clearBearerToken: async () => { tokenClears += 1; },
        ensureBearerHydrated: async () => {},
        getBearerToken: () => {
          tokenReads += 1;
          return token;
        },
        setBearerToken: async () => {},
      };
    }
    return require(id);
  };
  new Function("require", "module", "exports", apiRestJavaScript)(
    localRequire,
    loaded,
    loaded.exports,
  );
  return {
    api: loaded.exports,
    tokenReads: () => tokenReads,
    tokenClears: () => tokenClears,
  };
}

test("production script policy uses a nonce without unsafe-inline", () => {
  const policy = buildContentSecurityPolicy({ nonce: "abc123_-" });
  const scriptDirective = policy.split("; ").find((directive) => directive.startsWith("script-src "));

  assert.equal(scriptDirective, "script-src 'self' 'nonce-abc123_-' 'strict-dynamic'");
  assert.ok(!scriptDirective.includes("'unsafe-inline'"));
  assert.ok(policy.includes("script-src-attr 'none'"));
});

test("hosted profiles do not allow arbitrary plain-http connections", () => {
  const policy = buildContentSecurityPolicy({ nonce: "abc123", deploymentProfile: "public_demo" });

  assert.ok(policy.includes("connect-src 'self' http://localhost:8000 https:"));
  assert.ok(!policy.includes("connect-src 'self' http: https:"));
});

test("policy rejects a nonce that could inject another directive", () => {
  assert.throws(
    () => buildContentSecurityPolicy({ nonce: "abc'; script-src *" }),
    /Invalid CSP nonce/,
  );
});

test("cookie backend rejects loopback aliases that browsers treat as different sites", () => {
  const localhostPage = { protocol: "http:", hostname: "localhost" };
  const ipPage = { protocol: "http:", hostname: "127.0.0.1" };

  assert.equal(
    cookieBackendMatchesPage("http://localhost:8000/api/v1", localhostPage),
    true,
  );
  assert.equal(
    cookieBackendMatchesPage("http://localhost:8000/api/v1", ipPage),
    false,
  );
  assert.equal(
    cookieBackendMatchesPage("http://127.0.0.1:8000/api/v1", localhostPage),
    false,
  );
  assert.equal(
    cookieBackendMatchesPage("https://localhost:8000/api/v1", localhostPage),
    false,
  );
});

test("cookie backend resolves relative references before enforcing exact scheme and hostname", () => {
  const page = { protocol: "http:", hostname: "localhost" };

  assert.equal(cookieBackendMatchesPage("/api/v1", page), true);
  assert.equal(cookieBackendMatchesPage("//127.0.0.1:8000/api/v1", page), false);
  assert.equal(cookieBackendMatchesPage("\\\\127.0.0.1:8000\\api\\v1", page), false);
  assert.equal(cookieBackendMatchesPage("/\\127.0.0.1:8000/api/v1", page), false);
  assert.equal(cookieBackendMatchesPage("\t//127.0.0.1:8000/api/v1", page), false);
  assert.equal(cookieBackendMatchesPage("http://[::1", page), false);
});

test("loopback rewrite preserves the configured backend port and path", () => {
  const page = { protocol: "http:", hostname: "127.0.0.1" };

  assert.equal(
    rewriteLoopbackBackendForPage("http://localhost:8123/custom/api/v1", page),
    "http://127.0.0.1:8123/custom/api/v1",
  );
  assert.equal(rewriteLoopbackBackendForPage("//localhost:8123/api/v1", page), "");
  assert.equal(rewriteLoopbackBackendForPage("http:\\\\localhost:8123\\api\\v1", page), "");
  assert.equal(rewriteLoopbackBackendForPage("https://localhost:8123/api/v1", page), "");
});

test("loopback detection covers hostname and IP spelling tricks", () => {
  for (const hostname of (
    ["localhost", "localhost.", "api.localhost", "127.0.0.1", "127.0.0.2", "0.0.0.0", "[::]", "[::1]", "[::ffff:7f00:1]"]
  )) {
    assert.equal(isLoopbackHostname(hostname), true, hostname);
  }
  assert.equal(isLoopbackHostname("100.91.122.124"), false);
  assert.equal(isLoopbackHostname("desktop.tailnet.ts.net"), false);
});

test("private bridge detection accepts only RFC1918, Tailscale, and trusted tailnet names", () => {
  for (const hostname of [
    "10.0.0.1",
    "172.16.0.1",
    "172.31.255.255",
    "192.168.1.20",
    "100.64.0.1",
    "100.127.255.254",
    "desktop.tailnet-name.ts.net",
  ]) {
    assert.equal(isPrivateBridgeHostname(hostname), true, hostname);
  }
  for (const hostname of [
    "172.15.255.255",
    "172.32.0.1",
    "100.63.255.255",
    "100.128.0.1",
    "8.8.8.8",
    "evil.example",
    "ts.net.evil.example",
    "999.168.1.1",
    "192.168.1",
    "[fd00::1]",
    "[2001:db8::1]",
  ]) {
    assert.equal(isPrivateBridgeHostname(hostname), false, hostname);
  }
});

test("web resolution rewrites only the loopback hostname and retains configurable ports", () => {
  withBackendUrl(
    {
      env: "http://localhost:8123/custom/api/v1",
      page: { protocol: "http:", hostname: "127.0.0.1", port: "3210" },
    },
    (backendUrl) => {
      assert.deepEqual(backendUrl.getBackendResolution(), {
        url: "http://127.0.0.1:8123/custom/api/v1",
        source: "env",
      });
    },
  );
});

test("web resolution rejects a cross-host network-path env instead of bypassing cookie policy", () => {
  withBackendUrl(
    { env: "//127.0.0.1:8123/api/v1" },
    (backendUrl) => {
      assert.deepEqual(backendUrl.getBackendResolution(), {
        url: "http://localhost:8000/api/v1",
        source: "derived",
      });
    },
  );
});

test("web resolution rejects a bare root base that would become a network-path request", () => {
  withBackendUrl(
    { env: "/" },
    (backendUrl) => {
      const resolution = backendUrl.getBackendResolution();
      assert.deepEqual(resolution, {
        url: "http://localhost:8000/api/v1",
        source: "derived",
      });
      assert.notEqual(`${resolution.url}/auth/login`, "//auth/login");
    },
  );

  withBackendUrl(
    { env: "/api/v1/" },
    (backendUrl) => {
      assert.deepEqual(backendUrl.getBackendResolution(), {
        url: "/api/v1",
        source: "env",
      });
    },
  );
});

test("configured backend values cannot inject query or fragment into joined API paths", () => {
  for (const env of [
    "http://localhost:8000/api/v1?next=//evil.example",
    "http://localhost:8000/api/v1#ignored",
  ]) {
    withBackendUrl({ env }, (backendUrl) => {
      assert.deepEqual(backendUrl.getBackendResolution(), {
        url: "http://localhost:8000/api/v1",
        source: "derived",
      });
    });
  }

  withBackendUrl(
    {
      bearer: true,
      env: "https://desktop.tailnet.ts.net/api/v1?token=wrong-place",
    },
    (backendUrl) => {
      assert.deepEqual(backendUrl.getBackendResolution(), {
        url: "",
        source: "not_configured",
      });
    },
  );
});

test("mobile bearer mode rejects loopback overrides, env values, and derived URLs", () => {
  withBackendUrl(
    {
      bearer: true,
      env: "http://localhost:8000/api/v1",
      stored: "http://127.0.0.2:8000/api/v1",
      page: { protocol: "https:", hostname: "localhost", port: "" },
    },
    (backendUrl) => {
      assert.deepEqual(backendUrl.getBackendResolution(), { url: "", source: "not_configured" });
    },
  );

  withBackendUrl(
    {
      bearer: true,
      page: { protocol: "https:", hostname: "localhost", port: "" },
    },
    (backendUrl) => {
      assert.deepEqual(backendUrl.getBackendResolution(), { url: "", source: "not_configured" });
    },
  );
});

test("mobile bearer mode accepts an explicit non-loopback bridge", () => {
  withBackendUrl(
    {
      bearer: true,
      env: "https://built-in.tailnet.ts.net/api/v1",
      stored: "http://100.91.122.124:8123/api/v1",
      page: { protocol: "https:", hostname: "localhost", port: "" },
    },
    (backendUrl) => {
      assert.deepEqual(backendUrl.getBackendResolution(), {
        url: "http://100.91.122.124:8123/api/v1",
        source: "override",
      });
    },
  );
});

test("mobile bearer mode requires HTTPS for public or unclassifiable backends", () => {
  for (const env of [
    "http://evil.example/api/v1",
    "http://8.8.8.8/api/v1",
    "http://[2001:db8::1]/api/v1",
    "http://999.168.1.1/api/v1",
    "http://10.1/api/v1",
    "http://0x0a000001/api/v1",
    "http://012.0.0.1/api/v1",
  ]) {
    withBackendUrl(
      {
        bearer: true,
        env,
        page: { protocol: "https:", hostname: "localhost", port: "" },
      },
      (backendUrl) => {
        assert.deepEqual(backendUrl.getBackendResolution(), {
          url: "",
          source: "not_configured",
        });
      },
    );
  }

  withBackendUrl(
    {
      bearer: true,
      env: "https://api.example.com/api/v1",
      page: { protocol: "https:", hostname: "localhost", port: "" },
    },
    (backendUrl) => {
      assert.deepEqual(backendUrl.getBackendResolution(), {
        url: "https://api.example.com/api/v1",
        source: "env",
      });
    },
  );
});

test("backend URL normalization rejects browser host-confusion forms", () => {
  withBackendUrl({}, (backendUrl) => {
    assert.equal(backendUrl.normalizeBackendUrl("//127.0.0.1:8000"), "");
    assert.equal(backendUrl.normalizeBackendUrl("\\\\127.0.0.1:8000"), "");
    assert.equal(backendUrl.normalizeBackendUrl("100.91.122.124:8000"), "http://100.91.122.124:8000/api/v1");
    assert.equal(backendUrl.normalizeBackendUrl("http://localhost:8000?redirect=evil"), "");
    assert.equal(backendUrl.normalizeBackendUrl("http://localhost:8000/#fragment"), "");
  });
});

test("connection probes use the same accepted-URL policy as application requests", () => {
  const connection = fs.readFileSync(path.join(__dirname, "../lib/connection.ts"), "utf8");
  assert.match(connection, /resolveBackendCandidateUrl\(rawUrl\)/);
  assert.doesNotMatch(connection, /normalizeBackendUrl\(rawUrl\)/);
});

test("Backend Bridge save probes the effective accepted URL", () => {
  const card = fs.readFileSync(
    path.join(__dirname, "../components/settings/BackendBridgeCard.tsx"),
    "utf8",
  );
  assert.match(card, /testBackendConnection\(effective\.url\)/);
  assert.doesNotMatch(card, /testBackendConnection\(normalized\)/);
});

test("mobile without a bridge fails before fetch or bearer-header construction", async () => {
  const previousFetch = global.fetch;
  let fetchCalls = 0;
  global.fetch = async () => {
    fetchCalls += 1;
    throw new Error("fetch must not be reached");
  };

  try {
    const { api, tokenReads } = loadApiRest();
    const calls = [
      () => api.authApi.me(),
      () => api.driveApi.upload({}),
      () => api.driveApi.download("file-id"),
      () => api.knowledgeApi.uploadDocument({}),
    ];
    for (const call of calls) {
      await assert.rejects(call(), (error) => {
        assert.equal(error.code, "BRIDGE_REQUIRED");
        return true;
      });
    }
    assert.equal(fetchCalls, 0);
    assert.equal(tokenReads(), 0);
  } finally {
    global.fetch = previousFetch;
  }
});

test("logout only clears bearer state after backend-confirmed revocation", () => {
  assert.match(apiRestSource, /const result = await request<\{ logged_out: boolean \}>\("\/auth\/logout"/);
  assert.doesNotMatch(
    apiRestSource,
    /logout:\s*async\s*\(\)\s*=>\s*\{[\s\S]*?finally\s*\{[\s\S]*?clearBearerToken/,
  );

  const sidebar = fs.readFileSync(
    path.join(__dirname, "../components/layout/Sidebar.tsx"),
    "utf8",
  );
  assert.doesNotMatch(sidebar, /authApi\.logout\(\)\.catch\(\(\) => \{\}\)/);
  assert.match(sidebar, /await authApi\.logout\(\);[\s\S]*?clearAuth\(\);/);
  assert.match(sidebar, /role="alert"/);
});

test("failed backend logout retains the bearer credential for an honest retry", async () => {
  const previousFetch = global.fetch;
  try {
    global.fetch = async () => ({
      ok: false,
      status: 503,
      json: async () => ({ status: "error", error_code: "UNAVAILABLE", message: "retry" }),
    });
    const failed = loadApiRest({ baseUrl: "https://bridge.example/api/v1" });
    await assert.rejects(failed.api.authApi.logout(), /retry/);
    assert.equal(failed.tokenClears(), 0);

    global.fetch = async () => ({
      ok: true,
      status: 200,
      json: async () => ({ status: "success", data: { logged_out: true } }),
    });
    const succeeded = loadApiRest({ baseUrl: "https://bridge.example/api/v1" });
    await succeeded.api.authApi.logout();
    assert.equal(succeeded.tokenClears(), 1);
  } finally {
    global.fetch = previousFetch;
  }
});

test("frontend rejects a legacy false Supabase-connect success payload", async () => {
  const previousFetch = global.fetch;
  global.fetch = async () => new Response(
    JSON.stringify({
      status: "success",
      data: { connected: false },
      message: "Supabase Auth connected",
    }),
    { status: 200, headers: { "content-type": "application/json" } },
  );

  try {
    const { api } = loadApiRest({ baseUrl: "https://api.example.com/api/v1" });
    await assert.rejects(
      api.settingsApi.connectSupabase("password-is-not-logged"),
      (error) => {
        assert.equal(error.code, "SUPABASE_CONNECT_FAILED");
        assert.equal(error.statusCode, 502);
        return true;
      },
    );

    const modal = fs.readFileSync(
      path.join(__dirname, "../components/settings/IntegrationConfigModal.tsx"),
      "utf8",
    );
    assert.match(modal, /if \(!result\.connected\)[\s\S]*setConnectPassword\(""\)/);
  } finally {
    global.fetch = previousFetch;
  }
});
