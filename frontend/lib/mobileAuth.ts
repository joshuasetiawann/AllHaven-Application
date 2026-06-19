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

type PreferencesApi = Pick<
  typeof import("@capacitor/preferences").Preferences,
  "get" | "set" | "remove"
>;

// Lazily load the native plugin only in mobile builds (keeps it out of the
// desktop bundle entirely). Do not return the plugin object itself from an
// async function: Capacitor web plugins expose a `then` trap, so promise
// resolution treats the plugin as a thenable and throws `Preferences.then()`.
async function preferences(): Promise<PreferencesApi> {
  const { Preferences } = await import("@capacitor/preferences");
  return {
    get: Preferences.get.bind(Preferences),
    set: Preferences.set.bind(Preferences),
    remove: Preferences.remove.bind(Preferences),
  };
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

// Memoised one-time hydration. Every authenticated request awaits this before
// reading the in-memory token, so a cold start can't fire API calls with no
// Authorization header (which would 401 and bounce the user back to /login).
// No-op (resolved) on web/desktop. setBearerToken/clearBearerToken keep memToken
// correct afterwards, so memoising the first read is safe across login/logout.
let hydration: Promise<void> | null = null;
export function ensureBearerHydrated(): Promise<void> {
  if (!BEARER_MODE) return Promise.resolve();
  if (!hydration) hydration = hydrateBearerToken();
  return hydration;
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
