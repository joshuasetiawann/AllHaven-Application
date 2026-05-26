// Local UI preferences (Settings page). These are genuine, device-local
// preferences stored in localStorage — never faked cloud features.

export interface Prefs {
  glass: boolean; // glassmorphism blur on panels
  compact: boolean; // denser layout
}

const KEY = "coreos_prefs";

export const DEFAULT_PREFS: Prefs = { glass: true, compact: false };

export function loadPrefs(): Prefs {
  if (typeof window === "undefined") return DEFAULT_PREFS;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return DEFAULT_PREFS;
    return { ...DEFAULT_PREFS, ...(JSON.parse(raw) as Partial<Prefs>) };
  } catch {
    return DEFAULT_PREFS;
  }
}

export function savePrefs(prefs: Prefs): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(KEY, JSON.stringify(prefs));
  applyPrefs(prefs);
}

/** Apply preferences to the document root (CSS variables / data attributes). */
export function applyPrefs(prefs: Prefs): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.style.setProperty("--glass-blur", prefs.glass ? "14px" : "0px");
  root.style.setProperty("--panel-alpha", prefs.glass ? "0.72" : "0.95");
  root.setAttribute("data-density", prefs.compact ? "compact" : "comfortable");
}
