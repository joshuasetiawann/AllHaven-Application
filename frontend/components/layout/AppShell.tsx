"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";
import { Loading } from "@/components/ui/States";
import { authApi } from "@/lib/api";
import { clearAuth, setStoredUser } from "@/lib/auth";
import { hydrateBearerToken } from "@/lib/mobileAuth";
import { applyPrefs, loadPrefs } from "@/lib/prefs";
import { DATA_MODE, getSupabase } from "@/lib/supabaseClient";
import { cn } from "@/lib/format";

const COLLAPSE_KEY = "allhaven.sidebar.collapsed";

// Set once the server confirms the session for this page-load. Navigating
// between dashboard pages then won't re-flash the full-screen session loader;
// a hard refresh resets it (module re-evaluated) and verifies again.
let authConfirmed = false;

export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState<boolean>(() => authConfirmed);
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
    // Supabase mode (mobile): restore the persisted session before the first
    // API call so RLS-scoped queries succeed. Bearer mode (web/desktop): load
    // the persisted bearer token into memory (no-op on web, cookie-authenticated).
    const hydrate = DATA_MODE
      ? getSupabase().then((sb) => sb.auth.getSession()).then(() => undefined)
      : hydrateBearerToken();

    hydrate
      .then(() => authApi.me())
      .then((me) => {
        if (!active) return;
        setStoredUser(me.user);
        authConfirmed = true;
        setReady(true);
      })
      .catch(() => {
        if (!active) return;
        authConfirmed = false;
        clearAuth();
        router.replace("/login");
      });
    return () => {
      active = false;
    };
  }, [router]);

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
      <div className="flex min-h-screen items-center justify-center">
        <Loading label="Checking your session…" />
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
