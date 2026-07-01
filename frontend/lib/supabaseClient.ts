// frontend/lib/supabaseClient.ts — lazy supabase-js singleton + DATA_MODE flag.
// Session is persisted via Capacitor Preferences so it survives app restarts.
import type { SupabaseClient } from "@supabase/supabase-js";

export const DATA_MODE = process.env.NEXT_PUBLIC_DATA_MODE === "supabase";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

let client: SupabaseClient | null = null;
let workspaceId: string | null = null;

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
  const { createClient } = await import("@supabase/supabase-js");
  client = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      storage: capacitorStorage,
      storageKey: "allhaven_supabase_session",
    },
  });
  return client;
}

export function getWorkspaceId(): string | null {
  return workspaceId;
}
export function setWorkspaceId(id: string | null): void {
  workspaceId = id;
}
