// Named connection modes layered on top of lib/backendUrl.ts (the single source
// of truth for the backend base URL). This module never normalises or resolves
// URLs itself — it only translates a user-friendly MODE into the right override
// state, then lets getApiBaseUrl() do the actual resolution.
//
//   • 'auto'      — no override; resolution falls through env → derived → localhost.
//   • 'localhost' — same as 'auto' (no override) so derived/localhost wins. We keep
//                   it as a distinct label because on desktop dev that's exactly the
//                   :3000 → :8000 same-host derivation, which is what most users mean.
//   • 'tailscale' — a saved cross-origin override (the mobile app's path to the
//                   desktop). On DESKTOP web a cross-site override is intentionally
//                   ignored by getApiBaseUrl() (SameSite cookie guard); on mobile
//                   (BEARER mode) it's honoured.
//
// The selected mode is remembered separately from the override so the UI can show
// the user's intent even when the override is empty.

import {
  clearBackendOverride,
  getApiBaseUrl,
  getApiBaseUrlSource,
  normalizeBackendUrl,
  setBackendOverride,
} from "@/lib/backendUrl";

export type ConnectionMode = "auto" | "localhost" | "tailscale";

const MODE_KEY = "allhaven.connection_mode";
const TAILSCALE_URL_KEY = "allhaven.tailscale_url";

/** Fired by backendUrl.ts on any override change; the switcher listens for it. */
export const BACKEND_CHANGED_EVENT = "allhaven:backend-changed";

function isMode(v: string | null): v is ConnectionMode {
  return v === "auto" || v === "localhost" || v === "tailscale";
}

/** The user's selected connection mode (default 'auto'). */
export function getConnectionMode(): ConnectionMode {
  if (typeof window === "undefined") return "auto";
  try {
    const v = window.localStorage.getItem(MODE_KEY);
    return isMode(v) ? v : "auto";
  } catch {
    return "auto";
  }
}

/** The last Tailscale URL the user saved (raw, as stored), or "" if none. */
export function getRememberedTailscaleUrl(): string {
  if (typeof window === "undefined") return "";
  try {
    return window.localStorage.getItem(TAILSCALE_URL_KEY) || "";
  } catch {
    return "";
  }
}

function rememberTailscaleUrl(url: string): void {
  if (typeof window === "undefined") return;
  try {
    if (url) window.localStorage.setItem(TAILSCALE_URL_KEY, url);
    else window.localStorage.removeItem(TAILSCALE_URL_KEY);
  } catch {
    /* private-mode / disabled storage — mode still applies via the override */
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
 * Apply a connection mode. For 'tailscale' pass the URL to point at; for
 * 'auto'/'localhost' the URL is ignored. Mutating the override via backendUrl.ts
 * already dispatches the 'allhaven:backend-changed' event, so listeners refresh
 * without a reload.
 */
export function setConnectionMode(mode: ConnectionMode, url?: string): void {
  persistMode(mode);
  if (mode === "tailscale") {
    const normalized = setBackendOverride(normalizeBackendUrl(url || ""));
    rememberTailscaleUrl(normalized);
  } else {
    // 'auto' and 'localhost' both clear the override so resolution falls through
    // to env → derived → localhost.
    clearBackendOverride();
  }
}

// Re-export the resolution helpers so the switcher can show the live URL/source
// without importing backendUrl.ts directly (and without duplicating any logic).
export { getApiBaseUrl, getApiBaseUrlSource, normalizeBackendUrl };
