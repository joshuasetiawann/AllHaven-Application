// Local, device-scoped storage abstraction.
//
// A thin, typed, SSR-safe layer over `localStorage` with namespacing and
// per-store versioning. It is deliberately small and synchronous, but the
// `Store<T>` shape is the only surface the rest of the app touches — so a
// future move to IndexedDB (or a backend table) is a drop-in replacement
// behind `defineStore`, not a rewrite of every call site.
//
// Never put secrets / API keys here — this is plain, unencrypted, local data.

const NS = "allhaven";

/** Build a fully-qualified, namespaced + versioned storage key. */
function storageKey(name: string, version: number): string {
  return `${NS}:${name}:v${version}`;
}

function hasWindow(): boolean {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

export interface Store<T> {
  /** Current value, or the provided fallback when absent/corrupt. */
  get(): T;
  /** Whether a value has actually been persisted (vs. returning the fallback). */
  exists(): boolean;
  /** Persist a value. No-op on the server. */
  set(value: T): void;
  /** Read-modify-write convenience. */
  update(fn: (current: T) => T): T;
  /** Remove the stored value (reverts to fallback). */
  clear(): void;
  /** Subscribe to cross-tab changes for this key. Returns an unsubscribe fn. */
  subscribe(listener: (value: T) => void): () => void;
}

/**
 * Define a typed, versioned local store.
 *
 * @param name      Logical store name (namespaced under `allhaven:`).
 * @param version   Bump to invalidate older shapes (old keys are simply ignored).
 * @param fallback  Value returned when nothing is stored or parsing fails.
 * @param migrate   Optional sanitiser/migrator applied to parsed values.
 */
export function defineStore<T>(
  name: string,
  version: number,
  fallback: T,
  migrate?: (raw: unknown) => T,
): Store<T> {
  const key = storageKey(name, version);

  const get = (): T => {
    if (!hasWindow()) return fallback;
    try {
      const raw = window.localStorage.getItem(key);
      if (raw == null) return fallback;
      const parsed = JSON.parse(raw) as unknown;
      return migrate ? migrate(parsed) : (parsed as T);
    } catch {
      return fallback;
    }
  };

  const exists = (): boolean => {
    if (!hasWindow()) return false;
    try {
      return window.localStorage.getItem(key) != null;
    } catch {
      return false;
    }
  };

  const set = (value: T): void => {
    if (!hasWindow()) return;
    try {
      window.localStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* quota / serialization errors are non-fatal for local prefs */
    }
  };

  const update = (fn: (current: T) => T): T => {
    const next = fn(get());
    set(next);
    return next;
  };

  const clear = (): void => {
    if (!hasWindow()) return;
    try {
      window.localStorage.removeItem(key);
    } catch {
      /* ignore */
    }
  };

  const subscribe = (listener: (value: T) => void): (() => void) => {
    if (!hasWindow()) return () => {};
    const handler = (e: StorageEvent) => {
      if (e.key !== key) return;
      listener(get());
    };
    window.addEventListener("storage", handler);
    return () => window.removeEventListener("storage", handler);
  };

  return { get, exists, set, update, clear, subscribe };
}

/** Remove every AllHaven-namespaced key (used by "clear all local data"). */
export function clearAllLocal(): number {
  if (!hasWindow()) return 0;
  const doomed: string[] = [];
  for (let i = 0; i < window.localStorage.length; i += 1) {
    const k = window.localStorage.key(i);
    if (k && k.startsWith(`${NS}:`)) doomed.push(k);
  }
  doomed.forEach((k) => window.localStorage.removeItem(k));
  return doomed.length;
}
