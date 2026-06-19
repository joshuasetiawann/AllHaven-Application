// frontend/lib/supabaseClient.ts — lazy supabase-js singleton + DATA_MODE flag.
// Session is persisted via Capacitor Preferences so it survives app restarts.
import type { SupabaseClient } from "@supabase/supabase-js";
import { setBearerToken, clearBearerToken } from "@/lib/mobileAuth";

export const DATA_MODE = process.env.NEXT_PUBLIC_DATA_MODE === "supabase";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";
const SUPABASE_FETCH_TIMEOUT_MS = 7000;
const WORKSPACE_ID_KEY = "allhaven.supabase.workspace_id";
const APP_USER_ID_KEY = "allhaven.supabase.app_user_id";

let client: SupabaseClient | null = null;
let workspaceId: string | null = null;
let appUserId: string | null = null;

export function hasSupabaseConfig(): boolean {
  return Boolean(SUPABASE_URL.trim() && SUPABASE_ANON_KEY.trim());
}

function readCachedId(key: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeCachedId(key: string, value: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (value) window.localStorage.setItem(key, value);
    else window.localStorage.removeItem(key);
  } catch {
    /* ignore unavailable storage; IDs are non-secret cache only */
  }
}

export function getAppUserId(): string | null {
  if (!appUserId) appUserId = readCachedId(APP_USER_ID_KEY);
  return appUserId;
}

export function setAppUserId(id: string | null): void {
  appUserId = id;
  writeCachedId(APP_USER_ID_KEY, id);
}

// Async storage backed by Capacitor Preferences so the session survives app restarts.
const capacitorStorage = {
  getItem: async (key: string) => {
    const { Preferences } = await import("@capacitor/preferences");
    return (await Preferences.get({ key })).value;
  },
  setItem: async (key: string, value: string) => {
    const { Preferences } = await import("@capacitor/preferences");
    await Preferences.set({ key, value });
  },
  removeItem: async (key: string) => {
    const { Preferences } = await import("@capacitor/preferences");
    await Preferences.remove({ key });
  },
};

export async function getSupabase(): Promise<SupabaseClient> {
  if (client) return client;
  if (DATA_MODE && !hasSupabaseConfig()) {
    throw new Error("Mobile build is missing Supabase URL or anon key. Set SUPABASE_URL and SUPABASE_ANON_KEY in the APK build environment.");
  }
  const { createClient } = await import("@supabase/supabase-js");
  const timeoutFetch: typeof fetch = async (input, init) => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), SUPABASE_FETCH_TIMEOUT_MS);
    const upstream = init?.signal;
    const abort = () => controller.abort();
    try {
      if (upstream) {
        if (upstream.aborted) controller.abort();
        else upstream.addEventListener("abort", abort, { once: true });
      }
      return await fetch(input, { ...init, signal: controller.signal });
    } finally {
      clearTimeout(timer);
      upstream?.removeEventListener?.("abort", abort);
    }
  };
  client = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    global: {
      fetch: timeoutFetch,
    },
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      storage: capacitorStorage,
      storageKey: "allhaven_supabase_session",
    },
  });
  // Keep the Backend Bridge bearer token in sync with the live Supabase session.
  // The bridge (Settings, AI providers, system, n8n, Ollama) authenticates with the
  // Supabase access_token, but the login page only cached the profile and never
  // persisted the token — so every bridge call went out with no Authorization header
  // and 401'd (which then cleared what little there was). onAuthStateChange fires on
  // the restored session (cold start), on sign-in, and on every ~1h token refresh, so
  // the bridge token is always present and fresh; it's cleared on sign-out.
  client.auth.onAuthStateChange((_event, session) => {
    if (session?.access_token) void setBearerToken(session.access_token);
    else void clearBearerToken();
  });
  return client;
}

export function getWorkspaceId(): string | null {
  if (!workspaceId) workspaceId = readCachedId(WORKSPACE_ID_KEY);
  return workspaceId;
}
export function setWorkspaceId(id: string | null): void {
  workspaceId = id;
  writeCachedId(WORKSPACE_ID_KEY, id);
}
