// Named connection modes layered on top of lib/backendUrl.ts (the single source of
// truth for the backend base URL). This module never normalises or resolves URLs itself
// — it translates a user-friendly MODE into the right override state, then lets
// getApiBaseUrl() do the actual resolution.
//
//   • 'local'   — no override; resolution falls through env → derived → localhost
//                 (the desktop's own backend on this machine).
//   • 'private' — Tailscale PRIVATE tunnel: a saved override pointing at your desktop
//                 over the tailnet (tailnet-only, e.g. via `tailscale serve`). This is
//                 the recommended, secure path for the mobile app.
//   • 'funnel'  — Tailscale FUNNEL: a saved override pointing at a PUBLIC Tailscale
//                 Funnel URL (reachable from the internet, if you enabled Funnel).
//
// 'private' and 'funnel' each remember their own URL so switching between them keeps
// both. On DESKTOP web a cross-site override is intentionally ignored by getApiBaseUrl()
// (SameSite cookie guard); on mobile (BEARER mode) it is honoured.

import {
  clearBackendOverride,
  getApiBaseUrl,
  getApiBaseUrlSource,
  normalizeBackendUrl,
  setBackendOverride,
} from "@/lib/backendUrl";

export type ConnectionMode = "local" | "private" | "funnel";

const MODE_KEY = "allhaven.connection_mode";
const PRIVATE_URL_KEY = "allhaven.tailscale_private_url";
const FUNNEL_URL_KEY = "allhaven.tailscale_funnel_url";

/** Fired by backendUrl.ts on any override change; the switcher listens for it. */
export const BACKEND_CHANGED_EVENT = "allhaven:backend-changed";

/** Where to send users who don't have Tailscale yet. */
export const TAILSCALE_DOWNLOAD_URL = "https://tailscale.com/download";

function isMode(v: string | null): v is ConnectionMode {
  return v === "local" || v === "private" || v === "funnel";
}

function urlKey(mode: ConnectionMode): string | null {
  return mode === "private" ? PRIVATE_URL_KEY : mode === "funnel" ? FUNNEL_URL_KEY : null;
}

/** The user's selected connection mode (default 'private' — the mobile app's main path). */
export function getConnectionMode(): ConnectionMode {
  if (typeof window === "undefined") return "private";
  try {
    const v = window.localStorage.getItem(MODE_KEY);
    return isMode(v) ? v : "private";
  } catch {
    return "private";
  }
}

/** The last URL the user saved for a given Tailscale mode (raw, as stored), or "". */
export function getRememberedUrl(mode: ConnectionMode): string {
  const key = urlKey(mode);
  if (typeof window === "undefined" || !key) return "";
  try {
    return window.localStorage.getItem(key) || "";
  } catch {
    return "";
  }
}

function rememberUrl(mode: ConnectionMode, url: string): void {
  const key = urlKey(mode);
  if (typeof window === "undefined" || !key) return;
  try {
    if (url) window.localStorage.setItem(key, url);
    else window.localStorage.removeItem(key);
  } catch {
    /* private-mode / disabled storage — the override write below still changes resolution */
  }
}

function persistMode(mode: ConnectionMode): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(MODE_KEY, mode);
  } catch {
    /* ignore — the override write below still changes real resolution */
  }
}

/**
 * Apply a connection mode. For 'private'/'funnel' pass the URL to point at (falls back
 * to that mode's remembered URL); for 'local' the URL is ignored and the override is
 * cleared. Mutating the override via backendUrl.ts dispatches 'allhaven:backend-changed',
 * so listeners refresh without a reload.
 */
export function setConnectionMode(mode: ConnectionMode, url?: string): void {
  persistMode(mode);
  if (mode === "local") {
    clearBackendOverride();
    return;
  }
  const raw = url !== undefined ? url : getRememberedUrl(mode);
  const normalized = setBackendOverride(normalizeBackendUrl(raw || ""));
  rememberUrl(mode, normalized);
}

// Re-export the resolution helpers so the switcher can show the live URL/source
// without importing backendUrl.ts directly (and without duplicating any logic).
export { getApiBaseUrl, getApiBaseUrlSource, normalizeBackendUrl };
