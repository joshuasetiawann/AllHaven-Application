"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";
import { Loading } from "@/components/ui/States";
import { authApi } from "@/lib/api";
import { clearAuth, setStoredUser } from "@/lib/auth";
import { applyPrefs, loadPrefs } from "@/lib/prefs";
import { cn } from "@/lib/format";

export function AppShell({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  // The credential is an HttpOnly cookie JS can't read, so the only honest
  // check is asking the server. Survives a refresh without exposing a token.
  useEffect(() => {
    let active = true;
    applyPrefs(loadPrefs());
    authApi
      .me()
      .then((me) => {
        if (!active) return;
        setStoredUser(me.user);
        setReady(true);
      })
      .catch(() => {
        if (!active) return;
        clearAuth();
        router.replace("/login");
      });
    return () => {
      active = false;
    };
  }, [router]);

  // Close the mobile drawer on route change.
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loading label="Checking your session…" />
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      {/* Desktop sidebar */}
      <div className="fixed inset-y-0 left-0 z-40 hidden lg:block">
        <Sidebar pathname={pathname} />
      </div>

      {/* Mobile drawer */}
      <div className={cn("fixed inset-0 z-50 lg:hidden", mobileOpen ? "" : "pointer-events-none")}>
        <div
          className={cn(
            "absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity",
            mobileOpen ? "opacity-100" : "opacity-0",
          )}
          onClick={() => setMobileOpen(false)}
        />
        <div
          className={cn(
            "absolute inset-y-0 left-0 transition-transform duration-200",
            mobileOpen ? "translate-x-0" : "-translate-x-full",
          )}
        >
          <Sidebar pathname={pathname} onNavigate={() => setMobileOpen(false)} />
        </div>
      </div>

      <div className="lg:pl-[260px]">
        <Topbar onMenu={() => setMobileOpen(true)} />
        <main className="custom-scrollbar mx-auto max-w-[1320px] px-4 py-6 sm:px-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
