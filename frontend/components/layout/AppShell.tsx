"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";
import { BackendBridgeCard } from "@/components/settings/BackendBridgeCard";
import { ErrorState, Loading } from "@/components/ui/States";
import { ApiException, authApi } from "@/lib/api";
import { clearAuth, getStoredUser, setStoredUser } from "@/lib/auth";
import { ensureBearerHydrated } from "@/lib/mobileAuth";
import { applyPrefs, loadPrefs } from "@/lib/prefs";
import {
  DATA_MODE,
  getAppUserId,
  getSupabase,
  getWorkspaceId,
  hasSupabaseConfig,
  setAppUserId,
  setWorkspaceId,
} from "@/lib/supabaseClient";
import { cn } from "@/lib/format";

const COLLAPSE_KEY = "allhaven.sidebar.collapsed";

// Set once the server confirms the session for this page-load. Navigating
// between dashboard pages then won't re-flash the full-screen session loader;
// a hard refresh resets it (module re-evaluated) and verifies again.
let authConfirmed = false;

async function startupTimeout<T>(p: PromiseLike<T>, ms = 3000): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => {
      const err = new Error("Supabase is slow or unreachable. Check your internet connection and try again.");
      (err as { name?: string; code?: string }).name = "AbortError";
      (err as { name?: string; code?: string }).code = "TIMEOUT";
      reject(err);
    }, ms);
  });
  try {
    return await Promise.race([p as Promise<T>, timeout]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState<boolean>(() => authConfirmed);
  // Non-null when the session check failed for a non-auth reason (network /
  // timeout / server error). We show a retryable error instead of bouncing to
  // /login — the user may well be logged in; the server was just unreachable.
  const [authError, setAuthError] = useState<string | null>(null);
  // Bumping this re-runs the session check (the Retry button).
  const [authNonce, setAuthNonce] = useState(0);
  const [mobileOpen, setMobileOpen] = useState(false);
  // User's explicit rail preference (persisted). Only takes effect at ≥xl,
  // where there's room for the full sidebar; below xl the rail is forced.
  const [collapsed, setCollapsed] = useState(false);
  // Tracks the ≥xl breakpoint so width + content padding stay perfectly in
  // sync with the responsive rail (md = rail, xl = full unless collapsed).
  const [isXl, setIsXl] = useState(false);

  // The credential is an HttpOnly cookie JS can't read, so the only honest
  // check is asking the server. Survives a refresh without exposing a token.
  useEffect(() => {
    let active = true;
    applyPrefs(loadPrefs());
    setAuthError(null);
    const confirmSession = async () => {
      // Supabase mode (mobile): restore the persisted session before the first
      // API call so RLS-scoped queries succeed. If we already have a cached user
      // + workspace ID, let the app open immediately and refresh the profile in
      // the background; the phone should not sit on a full-screen loader just
      // because a profile query is slow.
      if (DATA_MODE) {
        if (!hasSupabaseConfig()) {
          throw new ApiException(
            "APK ini belum membawa konfigurasi Supabase. Rebuild APK dengan SUPABASE_URL dan SUPABASE_ANON_KEY.",
            "SUPABASE_CONFIG_MISSING",
            0,
          );
        }
        const sb = await getSupabase();
        const { data } = await startupTimeout(sb.auth.getSession(), 3000);
        if (!data.session) {
          throw new ApiException("Sesi Anda berakhir. Silakan masuk lagi.", "AUTH_SESSION_MISSING", 401);
        }
        const cachedUser = getStoredUser();
        if (cachedUser) {
          setStoredUser(cachedUser);
          authConfirmed = true;
          setReady(true);
          authApi.me()
            .then((me) => {
              if (!active) return;
              setStoredUser(me.user);
            })
            .catch((err) => {
              if (!active) return;
              const status = err instanceof ApiException ? err.statusCode : -1;
              if (status === 401) {
                authConfirmed = false;
                clearAuth();
                setAppUserId(null);
                setWorkspaceId(null);
                router.replace("/login");
              }
            });
          return null;
        }
      } else {
        // Bearer mode (web/desktop): load the persisted bearer token into memory
        // (memoised; no-op on cookie web, which authenticates via the session).
        await ensureBearerHydrated();
      }
      return authApi.me();
    };

    confirmSession()
      .then((me) => {
        if (!active) return;
        if (!me) return;
        setStoredUser(me.user);
        authConfirmed = true;
        setReady(true);
      })
      .catch((err) => {
        if (!active) return;
        // Only a real 401 means the session is invalid → log in again. A network
        // or timeout error does NOT (looks like "login never works"); surface it
        // with a Retry instead of bouncing back to /login.
        const status = err instanceof ApiException ? err.statusCode : -1;
        if (status === 401) {
          authConfirmed = false;
          clearAuth();
          setAppUserId(null);
          setWorkspaceId(null);
          router.replace("/login");
        } else {
          setAuthError(
            err instanceof Error ? err.message : "Couldn't reach the server.",
          );
        }
      });
    return () => {
      active = false;
    };
  }, [router, authNonce]);

  // Restore the persisted rail preference once on mount (guard for SSR).
  useEffect(() => {
    if (typeof window === "undefined") return;
    setCollapsed(window.localStorage.getItem(COLLAPSE_KEY) === "1");
  }, []);

  // Mirror the Tailwind `xl` breakpoint (1280px) into state.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mql = window.matchMedia("(min-width: 1280px)");
    const sync = () => setIsXl(mql.matches);
    sync();
    mql.addEventListener("change", sync);
    return () => mql.removeEventListener("change", sync);
  }, []);

  // Close the mobile drawer on route change.
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  const toggleCollapse = () => {
    setCollapsed((prev) => {
      const next = !prev;
      if (typeof window !== "undefined") {
        window.localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
      }
      return next;
    });
  };

  // Effective state: rail whenever below xl, otherwise honour the preference.
  const rail = !isXl || collapsed;

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center p-6">
        {authError ? (
          // The session check couldn't reach the server (network/timeout — not a
          // 401). On mobile that's usually the wrong backend URL, so offer the
          // Backend Bridge config right here; a successful test re-runs the check.
          <div className="w-full max-w-md">
            <ErrorState message={authError} onRetry={() => setAuthNonce((n) => n + 1)} />
            {!DATA_MODE ? (
              <div className="mt-5">
                <BackendBridgeCard onConnected={() => setAuthNonce((n) => n + 1)} />
              </div>
            ) : null}
          </div>
        ) : (
          <Loading label="Checking your session…" />
        )}
      </div>
    );
  }

  return (
    <div className="min-h-screen overflow-x-hidden">
      {/* Persistent sidebar — full rail on md+, hidden on mobile (drawer instead) */}
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-40 hidden transition-[width] duration-200 ease-out md:block",
          rail ? "md:w-[80px]" : "md:w-[280px]",
        )}
      >
        <Sidebar
          pathname={pathname}
          collapsed={rail}
          canToggle={isXl}
          onToggleCollapse={toggleCollapse}
        />
      </div>

      {/* Mobile drawer */}
      <div className={cn("fixed inset-0 z-50 md:hidden", mobileOpen ? "" : "pointer-events-none")}>
        <div
          className={cn(
            "absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity",
            mobileOpen ? "opacity-100" : "opacity-0",
          )}
          onClick={() => setMobileOpen(false)}
        />
        <div
          className={cn(
            "absolute inset-y-0 left-0 w-[min(86vw,280px)] transition-transform duration-200",
            mobileOpen ? "translate-x-0" : "-translate-x-full",
          )}
        >
          <Sidebar pathname={pathname} onNavigate={() => setMobileOpen(false)} />
        </div>
      </div>

      <div
        className={cn(
          "transition-[padding] duration-200 ease-out",
          rail ? "md:pl-[80px]" : "md:pl-[280px]",
        )}
      >
        <Topbar onMenu={() => setMobileOpen(true)} />
        {/* Keyed by route so page content gently animates in on navigation. */}
        <main
          key={pathname}
          className="custom-scrollbar mx-auto w-full max-w-[1480px] animate-page-in overflow-x-hidden px-3 py-4 sm:px-5 sm:py-5 lg:px-8 lg:py-7"
        >
          {children}
        </main>
      </div>
    </div>
  );
}
