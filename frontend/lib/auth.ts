// Browser auth state. The actual credential is an HttpOnly session cookie set
// by the backend — JavaScript can never read it, and NOTHING sensitive is kept
// in localStorage. We cache only the non-sensitive user profile for instant
// rendering; the real auth check is `GET /auth/me` (see AppShell).

import type { User } from "@/types";

const USER_KEY = "allhaven_user";
// Pre-cookie versions stored the bearer token here; always scrub it.
const LEGACY_TOKEN_KEY = "allhaven_token";
const SUPABASE_WORKSPACE_ID_KEY = "allhaven.supabase.workspace_id";
const SUPABASE_APP_USER_ID_KEY = "allhaven.supabase.app_user_id";

export function getStoredUser(): User | null {
  if (typeof window === "undefined") return null;
  window.localStorage.removeItem(LEGACY_TOKEN_KEY);
  const raw = window.localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

export function setStoredUser(user: User): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(LEGACY_TOKEN_KEY);
  window.localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(LEGACY_TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
  window.localStorage.removeItem(SUPABASE_WORKSPACE_ID_KEY);
  window.localStorage.removeItem(SUPABASE_APP_USER_ID_KEY);
}
