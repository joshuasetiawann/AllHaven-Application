// Bearer-token auth for the MOBILE (Capacitor) build only.
//
// The web/desktop build authenticates with an HttpOnly session cookie + CSRF
// header (see lib/api.ts). That cannot work reliably inside an Android WebView,
// where the bundled app's origin (https://localhost) differs from the API host,
// so cross-origin cookies get blocked. Instead the mobile build uses the bearer
// token the backend already issues alongside the cookie on login/register
// (backend/app/api/routers/auth.py: "cookie session + bearer token").
//
// The token is kept in NATIVE storage via @capacitor/preferences — NOT
// localStorage, which lib/auth.ts deliberately scrubs ("nothing sensitive in
// localStorage"). An in-memory mirror lets lib/api.ts read the token
// synchronously while building request headers; hydrateBearerToken() refills it
// from native storage on a cold start (call it before the first API request).
//
// Everything here is a no-op unless NEXT_PUBLIC_AUTH_MODE === "bearer", so the
// desktop build is completely unaffected and never loads @capacitor/preferences.

export const BEARER_MODE = process.env.NEXT_PUBLIC_AUTH_MODE === "bearer";

const TOKEN_KEY = "allhaven_bearer_token";

// Synchronous source of truth for request() headers. Mirrors native storage.
let memToken: string | null = null;

// Lazily load the native plugin only in mobile builds (keeps it out of the
// desktop bundle entirely).
async function preferences() {
  const { Preferences } = await import("@capacitor/preferences");
  return Preferences;
}

/** Token for the Authorization header, or null. Synchronous (in-memory). */
export function getBearerToken(): string | null {
  return memToken;
}

/** Load the persisted token into memory. Call before the first API request. */
export async function hydrateBearerToken(): Promise<void> {
  if (!BEARER_MODE) return;
  try {
    const Preferences = await preferences();
    const { value } = await Preferences.get({ key: TOKEN_KEY });
    memToken = value ?? null;
  } catch {
    memToken = null;
  }
}

/** Persist the token (memory + native storage) after a successful login. */
export async function setBearerToken(token: string): Promise<void> {
  memToken = token;
  if (!BEARER_MODE) return;
  try {
    const Preferences = await preferences();
    await Preferences.set({ key: TOKEN_KEY, value: token });
  } catch {
    /* memory copy still lets the current session work */
  }
}

/** Clear the token on logout or after a 401. */
export async function clearBearerToken(): Promise<void> {
  memToken = null;
  if (!BEARER_MODE) return;
  try {
    const Preferences = await preferences();
    await Preferences.remove({ key: TOKEN_KEY });
  } catch {
    /* memory already cleared */
  }
}
