// Single source of truth for the AllHaven backend base URL (the REST API root,
// which ends in /api/v1). The value is resolved PER REQUEST so a user can
// repoint the *installed* app at their desktop without a rebuild — this is what
// makes the mobile APK usable. Inside the Capacitor WebView the page origin is
// always https://localhost (the phone itself), so a baked-in or derived URL can
// never reach the desktop; the user must be able to set it at runtime.
//
// Resolution order (highest priority first):
//   1. User-saved override (Settings → Backend Bridge), kept in localStorage.
//      This is a NON-SECRET URL only — never a token or key. lib/auth.ts only
//      scrubs its own keys, so this value survives login/logout. The bearer
//      token stays in native @capacitor/preferences (see lib/mobileAuth.ts).
//   2. NEXT_PUBLIC_API_BASE_URL baked at build time (CI APK / hosted web).
//   3. Browser-derived: same scheme+host as the page on :8000 (desktop dev/LAN).
//   4. http://localhost:8000/api/v1 (SSR / final fallback).

const OVERRIDE_KEY = "allhaven.backend_base_url";

export type BackendUrlSource = "override" | "env" | "derived" | "fallback";

/**
 * Normalise whatever the user typed into a usable API root:
 *  - trims and drops trailing slashes,
 *  - tolerates a bare host (no scheme) by assuming http:// (Tailscale IPs),
 *  - ensures it ends in /api/v1 if no /api[/vN] segment is present,
 *  - leaves scheme/host/port intact (http or https, Tailscale IP or MagicDNS).
 * Returns "" for empty input.
 */
export function normalizeBackendUrl(raw: string): string {
  let s = (raw || "").trim();
  if (!s) return "";
  if (!/^https?:\/\//i.test(s)) s = `http://${s}`;
  s = s.replace(/\/+$/, "");
  if (!/\/api(\/v\d+)?$/i.test(s)) s = `${s}/api/v1`;
  return s;
}

/** The raw saved override, or "" if none. (Already normalised when saved.) */
export function getBackendOverride(): string {
  if (typeof window === "undefined") return "";
  try {
    return window.localStorage.getItem(OVERRIDE_KEY) || "";
  } catch {
    return "";
  }
}

/**
 * Persist (or clear, when given an empty/whitespace value) the override.
 * Returns the normalised value actually stored ("" when cleared).
 */
export function setBackendOverride(raw: string): string {
  const normalized = normalizeBackendUrl(raw);
  if (typeof window !== "undefined") {
    try {
      if (normalized) window.localStorage.setItem(OVERRIDE_KEY, normalized);
      else window.localStorage.removeItem(OVERRIDE_KEY);
    } catch {
      /* private-mode / disabled storage — fall back to env/derived resolution */
    }
  }
  return normalized;
}

/** Remove the override so resolution falls back to env/derived/localhost. */
export function clearBackendOverride(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(OVERRIDE_KEY);
  } catch {
    /* ignore */
  }
}

function fromEnv(): string {
  const v = process.env.NEXT_PUBLIC_API_BASE_URL;
  return v && v.trim() ? v.trim() : "";
}

function derived(): string {
  if (typeof window !== "undefined" && window.location?.hostname) {
    const { protocol, hostname } = window.location;
    return `${protocol}//${hostname}:8000/api/v1`;
  }
  return "";
}

/** The active API root, resolved fresh on every call (override → env → derived → localhost). */
export function getApiBaseUrl(): string {
  return (
    getBackendOverride() ||
    fromEnv() ||
    derived() ||
    "http://localhost:8000/api/v1"
  );
}

/** Which source is currently in effect — for honest status display in Settings. */
export function getApiBaseUrlSource(): BackendUrlSource {
  if (getBackendOverride()) return "override";
  if (fromEnv()) return "env";
  if (derived()) return "derived";
  return "fallback";
}
