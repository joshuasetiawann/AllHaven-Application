// Backend / Desktop-Bridge reachability helpers (v4.0 mobile parity).
//
// Backend-only features (Drive, Knowledge upload, integration secrets, n8n…) reach the
// REST backend. On mobile the backend is reached over Tailscale; when it isn't, we show
// a SetupRequiredState instead of a raw error or a "use desktop app" message.

import { ApiException, getApiBaseUrl } from "@/lib/api";
import { normalizeBackendUrl } from "@/lib/backendUrl";
import { BEARER_MODE, ensureBearerHydrated, getBearerToken } from "@/lib/mobileAuth";

/** True when an error means the backend/bridge is unreachable (vs a real app error). */
export function isBackendUnreachable(err: unknown): boolean {
  if (err instanceof ApiException) {
    if (err.code === "UNAVAILABLE_ON_MOBILE" || err.code === "BRIDGE_REQUIRED") return true;
    // 0 = network/CORS/abort; 502/503/504 = gateway/unreachable.
    if (err.statusCode === 0 || err.statusCode === 502 || err.statusCode === 503 || err.statusCode === 504) {
      return true;
    }
    return /timed out|could not (reach|connect)|network|failed to fetch|connection|unreachable/i.test(err.message);
  }
  return (
    err instanceof Error &&
    /failed to fetch|networkerror|timed out|timeout|connection|unreachable/i.test(err.message)
  );
}

/**
 * On mobile a backend-only feature can't run without the desktop bridge: treat an
 * unreachable backend OR a bridge 401 (token rejected / account not linked) as "needs
 * connection". The panel then shows a connect-state instead of a hard error — and the
 * 401 never logs the user out (handleUnauthorized is a no-op in bearer mode).
 */
export function needsBackendConnection(err: unknown): boolean {
  if (isBackendUnreachable(err)) return true;
  return BEARER_MODE && err instanceof ApiException && err.statusCode === 401;
}

/** Best-effort: is the REST backend reachable right now? (public /health, short timeout) */
export async function pingBackend(timeoutMs = 4000): Promise<boolean> {
  const base = getApiBaseUrl();
  if (!base) return false;
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${base}/health`, { signal: ctrl.signal });
    return res.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(t);
  }
}

// Shared, cached reachability so EVERY backend-only panel degrades fast from ONE probe
// instead of each independently waiting the full request timeout. The previous gate keyed
// off getApiBaseUrlSource()==='fallback', which is never true on the APK (the Tailscale
// URL is baked in as 'env'), so panels still spun ~6s each. A single short ping fixes that.
let _reachCache: { ok: boolean; at: number } | null = null;
let _reachInflight: Promise<boolean> | null = null;
const _REACH_TTL_MS = 8000;

/** Drop the cached reachability result (e.g. when the backend URL/mode changes). */
export function invalidateBackendReachable(): void {
  _reachCache = null;
  _reachInflight = null;
}

if (typeof window !== "undefined") {
  window.addEventListener("allhaven:backend-changed", invalidateBackendReachable);
}

/**
 * Cached, de-duplicated reachability check. Returns the cached value within an 8s window;
 * otherwise pings `/health` once (short timeout) and shares the in-flight promise across
 * concurrent callers. Use this to gate backend-only UI on mobile so it shows a clear
 * "connect a backend" state in ~2-3s instead of spinning for the full timeout.
 */
export async function backendReachable(timeoutMs = 2500): Promise<boolean> {
  const now = Date.now();
  if (_reachCache && now - _reachCache.at < _REACH_TTL_MS) return _reachCache.ok;
  if (_reachInflight) return _reachInflight;
  _reachInflight = pingBackend(timeoutMs).then((ok) => {
    _reachCache = { ok, at: Date.now() };
    _reachInflight = null;
    return ok;
  });
  return _reachInflight;
}

/** Honest result of a Test Connection against a specific (or the active) backend URL. */
export interface BackendTestResult {
  ok: boolean;
  /** "online" only when /health truly responded ok; otherwise a non-online status. */
  status: "online" | "auth_failed" | "error" | "unavailable" | "not_configured";
  message: string;
  /** HTTP status code from /health, when we got a response. */
  httpStatus?: number;
  /** Round-trip latency in ms, when reachable. */
  latencyMs?: number;
  /** Useful health metadata, when the envelope returned it (never secrets). */
  appVersion?: string;
  deploymentProfile?: string;
  /** The normalised base URL that was actually probed. */
  testedUrl: string;
}

/**
 * Probe GET {base}/health and return an HONEST status. "online" requires a real
 * 2xx response carrying the standard success envelope — never inferred from a
 * non-empty URL. Pass a raw URL to test before saving; omit to test the active one.
 */
export async function testBackendConnection(
  rawUrl?: string,
  timeoutMs = 6000,
): Promise<BackendTestResult> {
  const base = rawUrl !== undefined ? normalizeBackendUrl(rawUrl) : getApiBaseUrl();
  if (!base) {
    return { ok: false, status: "not_configured", message: "Desktop Bridge is not configured. Enter a backend URL only for Ollama/n8n desktop features.", testedUrl: "" };
  }
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  const startedAt = typeof performance !== "undefined" ? performance.now() : 0;
  try {
    const res = await fetch(`${base}/health`, { signal: ctrl.signal });
    const latencyMs = Math.max(0, Math.round((typeof performance !== "undefined" ? performance.now() : 0) - startedAt));
    let body: { status?: string; data?: { status?: string; app_version?: string; deployment_profile?: string } } | null = null;
    try {
      body = await res.json();
    } catch {
      body = null;
    }
    if (res.ok && body?.status === "success") {
      if (BEARER_MODE) {
        await ensureBearerHydrated();
        const token = getBearerToken();
        if (!token) {
          return {
            ok: false,
            status: "auth_failed",
            message: "Backend is online, but this app has no mobile login token. Sign in again, then retry.",
            httpStatus: 401,
            latencyMs,
            appVersion: body?.data?.app_version,
            deploymentProfile: body?.data?.deployment_profile,
            testedUrl: base,
          };
        }
        const authRes = await fetch(`${base}/auth/me`, {
          signal: ctrl.signal,
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!authRes.ok) {
          return {
            ok: false,
            status: "auth_failed",
            message: authRes.status === 401 || authRes.status === 403
              ? "Backend is online, but it does not trust this mobile login yet. Link Supabase on desktop or sign in on desktop once with the same account, then retry."
              : `Backend is online, but /auth/me returned HTTP ${authRes.status}.`,
            httpStatus: authRes.status,
            latencyMs,
            appVersion: body?.data?.app_version,
            deploymentProfile: body?.data?.deployment_profile,
            testedUrl: base,
          };
        }
      }
      return {
        ok: true,
        status: "online",
        message: `Online · responded in ${latencyMs} ms`,
        httpStatus: res.status,
        latencyMs,
        appVersion: body?.data?.app_version,
        deploymentProfile: body?.data?.deployment_profile,
        testedUrl: base,
      };
    }
    // Reached a server, but it isn't a healthy AllHaven backend at this path.
    return {
      ok: false,
      status: "error",
      message: `Reached the host, but /health returned HTTP ${res.status}. Check the URL path (it should end in /api/v1).`,
      httpStatus: res.status,
      testedUrl: base,
    };
  } catch (err) {
    const timedOut = err instanceof DOMException && err.name === "AbortError";
    return {
      ok: false,
      status: "unavailable",
      message: timedOut
        ? "Timed out — the host didn't respond. Check Tailscale, the URL, and that the backend is running with --host 0.0.0.0."
        : "Could not reach this URL. On mobile use a Tailscale URL (not localhost); confirm the backend is running.",
      testedUrl: base,
    };
  } finally {
    clearTimeout(t);
  }
}
