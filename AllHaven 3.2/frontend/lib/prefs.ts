// Local UI preferences (Settings page). These are genuine, device-local
// preferences stored in localStorage — never faked cloud features.

export interface Prefs {
  glass: boolean; // glassmorphism blur on panels
  compact: boolean; // denser layout
  language: AppLanguage; // preferred UI/AI response language
  theme: AppTheme; // app color mode
  accent: AppAccent; // primary color mood
}

const KEY = "allhaven_prefs";

export type AppLanguage = "id" | "en" | "zh-Hant";
export type AppTheme = "dark" | "light";
export type AppAccent = "cyan" | "emerald" | "violet" | "amber";

export const LANGUAGE_OPTIONS: Array<{ value: AppLanguage; label: string; helper: string }> = [
  { value: "id", label: "Bahasa Indonesia", helper: "AI menjawab natural dalam bahasa Indonesia." },
  { value: "en", label: "English", helper: "AI replies in concise English." },
  { value: "zh-Hant", label: "Mandarin Tradisional", helper: "AI 使用繁體中文回覆。" },
];

export const THEME_OPTIONS: Array<{ value: AppTheme; label: string; helper: string }> = [
  { value: "dark", label: "Dark", helper: "Command-center dark mode." },
  { value: "light", label: "Light", helper: "Brighter workspace for daylight use." },
];

export const ACCENT_OPTIONS: Array<{ value: AppAccent; label: string; swatch: string }> = [
  { value: "cyan", label: "Cyan", swatch: "#18E0D6" },
  { value: "emerald", label: "Emerald", swatch: "#22C55E" },
  { value: "violet", label: "Violet", swatch: "#8B5CF6" },
  { value: "amber", label: "Amber", swatch: "#F59E0B" },
];

export const DEFAULT_PREFS: Prefs = {
  glass: true,
  compact: false,
  language: "id",
  theme: "dark",
  accent: "cyan",
};

function valid<T extends string>(value: unknown, options: readonly T[], fallback: T): T {
  return options.includes(value as T) ? (value as T) : fallback;
}

function normalize(raw: Partial<Prefs>): Prefs {
  return {
    ...DEFAULT_PREFS,
    ...raw,
    language: valid(raw.language, LANGUAGE_OPTIONS.map((o) => o.value), DEFAULT_PREFS.language),
    theme: valid(raw.theme, THEME_OPTIONS.map((o) => o.value), DEFAULT_PREFS.theme),
    accent: valid(raw.accent, ACCENT_OPTIONS.map((o) => o.value), DEFAULT_PREFS.accent),
    glass: typeof raw.glass === "boolean" ? raw.glass : DEFAULT_PREFS.glass,
    compact: typeof raw.compact === "boolean" ? raw.compact : DEFAULT_PREFS.compact,
  };
}

export function loadPrefs(): Prefs {
  if (typeof window === "undefined") return DEFAULT_PREFS;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return DEFAULT_PREFS;
    return normalize(JSON.parse(raw) as Partial<Prefs>);
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
  root.setAttribute("data-theme", prefs.theme);
  root.setAttribute("data-accent", prefs.accent);
  root.lang = prefs.language;

  const metaTheme = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
  if (metaTheme) metaTheme.content = prefs.theme === "light" ? "#F6F8FB" : "#0A0C10";
}

export function responseLanguageLabel(language: AppLanguage): string {
  if (language === "en") return "English";
  if (language === "zh-Hant") return "Traditional Mandarin Chinese";
  return "Bahasa Indonesia";
}
