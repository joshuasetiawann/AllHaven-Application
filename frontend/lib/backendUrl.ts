// Single source of truth for the REST API root. Resolution happens per request
// so an installed app can be repointed at a desktop without rebuilding.
//
// Web/cookie resolution:
//   saved override -> build-time env -> same-host derived -> localhost fallback
// Mobile/bearer resolution:
//   saved non-loopback override -> build-time non-loopback env -> not configured
//
// A Capacitor page is served from https://localhost on the phone. Deriving or
// accepting a loopback backend there would target the phone, not the desktop,
// and could expose the bearer token to an unrelated local listener.

import { BEARER_MODE } from "@/lib/mobileAuth";
import {
  cookieBackendMatchesPage,
  isPrivateBridgeHostname,
  isLoopbackHostname,
  rewriteLoopbackBackendForPage,
} from "@/lib/backendUrlPolicy";

const OVERRIDE_KEY = "allhaven.backend_base_url";

export type BackendUrlSource = "override" | "env" | "derived" | "fallback" | "not_configured";

export interface BackendUrlResolution {
  url: string;
  source: BackendUrlSource;
}

/**
 * Normalise a user-entered host into an absolute HTTP(S) API root. Network-path
 * and backslash forms are rejected because browsers can interpret them as a
 * different host than their text suggests.
 */
export function normalizeBackendUrl(raw: string): string {
  let value = (raw || "").trim();
  if (!value) return "";
  if (value.includes("\\") || value.startsWith("/")) return "";
  if (!/^https?:\/\//i.test(value)) value = `http://${value}`;
  const parsed = parseAbsoluteHttpUrl(value);
  if (!parsed || parsed.search || parsed.hash) return "";
  let pathname = parsed.pathname.replace(/\/+$/, "");
  if (!/\/api(\/v\d+)?$/i.test(pathname)) {
    pathname = `${pathname}/api/v1`;
  }
  parsed.pathname = pathname;
  return parsed.href;
}

/** The raw saved override, or "" if none. */
export function getBackendOverride(): string {
  if (typeof window === "undefined") return "";
  try {
    return window.localStorage.getItem(OVERRIDE_KEY) || "";
  } catch {
    return "";
  }
}

/** Persist an override, or clear it when the input is empty/invalid. */
export function setBackendOverride(raw: string): string {
  const normalized = normalizeBackendUrl(raw);
  if (typeof window !== "undefined") {
    try {
      if (normalized) window.localStorage.setItem(OVERRIDE_KEY, normalized);
      else window.localStorage.removeItem(OVERRIDE_KEY);
    } catch {
      /* private-mode / disabled storage: fall through to env/derived resolution */
    }
  }
  return normalized;
}

export function clearBackendOverride(): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(OVERRIDE_KEY);
  } catch {
    /* ignore */
  }
}

function fromEnv(): string {
  const value = process.env.NEXT_PUBLIC_API_BASE_URL;
  return value && value.trim() ? value.trim() : "";
}

function parseAbsoluteHttpUrl(raw: string): URL | null {
  const value = String(raw || "").trim();
  if (!/^https?:\/\//i.test(value) || value.includes("\\")) return null;
  try {
    const parsed = new URL(value);
    if ((parsed.protocol !== "http:" && parsed.protocol !== "https:") || parsed.username || parsed.password) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

function safeRootRelativeUrl(raw: string): string {
  const value = String(raw || "").trim();
  if (!value.startsWith("/") || value.startsWith("//") || value.includes("\\")) return "";
  try {
    const sentinel = new URL("http://allhaven.invalid/");
    const parsed = new URL(value, sentinel);
    if (parsed.origin !== sentinel.origin || parsed.search || parsed.hash) return "";
    // The API client appends paths beginning with `/`. A bare `/` base would
    // produce `//auth/login`, which browsers interpret as a network-path URL to
    // host `auth`. Require an actual base path and strip trailing separators.
    return parsed.pathname.replace(/\/+$/, "");
  } catch {
    return "";
  }
}

function mobileConfiguredUrl(raw: string): string {
  const parsed = parseAbsoluteHttpUrl(raw);
  if (!parsed || parsed.search || parsed.hash || isLoopbackHostname(parsed.hostname)) return "";
  // A native request carries a bearer credential. Permit cleartext only across
  // the documented private LAN/Tailscale bridge; public and unclassifiable
  // targets must use HTTPS so the token cannot leave the device in plaintext.
  if (parsed.protocol === "http:") {
    // WHATWG URL parsing canonicalises ambiguous IPv4 spellings (`10.1`, hex,
    // octal) before this point. Require the user/config to have supplied either
    // a conventional dotted-decimal literal or a trusted tailnet DNS name so a
    // visually surprising address can never become bearer-eligible.
    const authority = String(raw).match(/^http:\/\/([^/?#]+)/i)?.[1] || "";
    const rawHost = authority.replace(/^[^@]*@/, "").replace(/:\d+$/, "").toLowerCase();
    const explicitDottedDecimal = (
      /^\d{1,3}(?:\.\d{1,3}){3}$/.test(rawHost)
      && parsed.hostname === rawHost
    );
    const explicitPrivateHost = explicitDottedDecimal
      || /^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+ts\.net\.?$/.test(rawHost);
    if (!explicitPrivateHost || !isPrivateBridgeHostname(parsed.hostname)) return "";
  }
  parsed.pathname = parsed.pathname.replace(/\/+$/, "");
  return parsed.href;
}

function cookieConfiguredUrl(raw: string): string {
  const value = String(raw || "").trim();
  if (!value) return "";

  const absolute = parseAbsoluteHttpUrl(value);
  const relative = safeRootRelativeUrl(value);
  if (absolute && (absolute.search || absolute.hash)) return "";
  if (!absolute && !relative) return "";
  const candidate = relative || value;
  if (typeof window === "undefined") return candidate;

  if (cookieBackendMatchesPage(candidate, window.location)) return candidate;

  // Production-local Docker bakes `localhost:<configured backend port>`, but
  // users can open the frontend as 127.0.0.1. Rewrite only this explicit
  // loopback-alias case, retaining the configured port and path.
  return absolute ? rewriteLoopbackBackendForPage(value, window.location) : "";
}

function configuredUrl(raw: string): string {
  return BEARER_MODE ? mobileConfiguredUrl(raw) : cookieConfiguredUrl(raw);
}

/** Apply the active authentication policy to a user-entered backend URL. */
export function resolveBackendCandidateUrl(raw: string): string {
  const normalized = normalizeBackendUrl(raw);
  return normalized ? configuredUrl(normalized) : "";
}

function derivedWebUrl(): string {
  if (BEARER_MODE || typeof window === "undefined" || !window.location?.hostname) return "";
  const { protocol, hostname, port } = window.location;
  if (port === "3000") return `${protocol}//${hostname}:8000/api/v1`;
  return `${protocol}//${hostname}${port ? `:${port}` : ""}/api/v1`;
}

/** Resolve URL and source atomically so status UI cannot describe another URL. */
export function getBackendResolution(): BackendUrlResolution {
  const override = configuredUrl(getBackendOverride());
  if (override) return { url: override, source: "override" };

  const env = configuredUrl(fromEnv());
  if (env) return { url: env, source: "env" };

  if (BEARER_MODE) return { url: "", source: "not_configured" };

  const derived = derivedWebUrl();
  if (derived) return { url: derived, source: "derived" };
  return { url: "http://localhost:8000/api/v1", source: "fallback" };
}

export function getApiBaseUrl(): string {
  return getBackendResolution().url;
}

export function getApiBaseUrlSource(): BackendUrlSource {
  return getBackendResolution().source;
}
