// Backend / Desktop-Bridge reachability helpers (v4.0 mobile parity).
//
// Backend-only features (Drive, Knowledge upload, integration secrets, n8n…) reach the
// REST backend. On mobile the backend is reached over Tailscale; when it isn't, we show
// a SetupRequiredState instead of a raw error or a "use desktop app" message.

import { ApiException, API_BASE_URL } from "@/lib/api";

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

/** Best-effort: is the REST backend reachable right now? (public /health, short timeout) */
export async function pingBackend(timeoutMs = 4000): Promise<boolean> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${API_BASE_URL}/health`, { signal: ctrl.signal });
    return res.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(t);
  }
}
