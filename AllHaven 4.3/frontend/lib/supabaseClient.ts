// frontend/lib/supabaseClient.ts — lazy supabase-js singleton + DATA_MODE flag.
// Native sessions are persisted in iOS Keychain / Android Keystore-backed
// encrypted storage so they survive app restarts without plaintext credentials.
import type { SupabaseClient } from "@supabase/supabase-js";
import { ApiException } from "@/lib/apiRest";
import { setBearerToken, clearBearerToken } from "@/lib/mobileAuth";
import { credentialStorage } from "@/lib/credentialStorage";

export const DATA_MODE = process.env.NEXT_PUBLIC_DATA_MODE === "supabase";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

let client: SupabaseClient | null = null;
let workspaceId: string | null = null;
let appUserId: string | null = null;

export function getAppUserId(): string | null { return appUserId; }
export function setAppUserId(id: string | null): void { appUserId = id; }

export async function getSupabase(): Promise<SupabaseClient> {
  if (client) return client;
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
    throw new ApiException(
      "Mobile login is missing Supabase configuration. Rebuild the APK with NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.",
      "SUPABASE_NOT_CONFIGURED",
      500,
    );
  }
  const { createClient } = await import("@supabase/supabase-js");
  client = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      storage: credentialStorage,
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
  return workspaceId;
}
export function setWorkspaceId(id: string | null): void {
  workspaceId = id;
}
