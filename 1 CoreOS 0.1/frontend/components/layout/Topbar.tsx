"use client";

import { useRouter } from "next/navigation";
import { LogOut, Search } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { clearAuth, getStoredUser } from "@/lib/auth";

export function Topbar({ title, subtitle }: { title: string; subtitle?: string }) {
  const router = useRouter();
  const user = getStoredUser();

  const signOut = () => {
    clearAuth();
    router.replace("/login");
  };

  const initial = (user?.full_name || user?.email || "U").charAt(0).toUpperCase();

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border bg-bg/70 px-6 backdrop-blur-[12px]">
      <div>
        <h1 className="text-[17px] font-semibold tracking-tight text-content">{title}</h1>
        {subtitle ? <p className="text-[13px] text-content-muted">{subtitle}</p> : null}
      </div>

      <div className="flex items-center gap-3">
        <div className="hidden items-center gap-2 rounded-md border border-border bg-surface-input px-3 py-1.5 text-content-subtle md:flex">
          <Search size={15} />
          <span className="text-[13px]">Search is not wired in this MVP</span>
        </div>

        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-full border border-border bg-surface-high text-[13px] font-medium text-primary">
            {initial}
          </div>
          <div className="hidden leading-tight sm:block">
            <p className="max-w-[160px] truncate text-[13px] font-medium text-content">
              {user?.full_name || user?.email || "Account"}
            </p>
            <p className="label-mono">Owner</p>
          </div>
        </div>

        <Button variant="ghost" size="sm" onClick={signOut} aria-label="Sign out">
          <LogOut size={15} />
          <span className="hidden sm:inline">Sign Out</span>
        </Button>
      </div>
    </header>
  );
}
