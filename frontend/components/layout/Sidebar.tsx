"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { LogOut, LifeBuoy, Plus, ShieldCheck } from "lucide-react";
import { APP_VERSION, FUTURE_NAV, PRIMARY_NAV } from "@/components/layout/nav";
import { clearAuth } from "@/lib/auth";
import { cn } from "@/lib/format";

export function Sidebar({
  pathname,
  onNavigate,
}: {
  pathname: string;
  onNavigate?: () => void;
}) {
  const router = useRouter();

  const isActive = (href: string) =>
    href === "/dashboard" ? pathname === href : pathname.startsWith(href);

  const signOut = () => {
    clearAuth();
    router.replace("/login");
  };

  return (
    <div className="flex h-full w-[260px] flex-col border-r border-border bg-bg-deep/95">
      {/* Brand */}
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-fg shadow-glow-primary">
          <ShieldCheck size={18} />
        </div>
        <div className="leading-tight">
          <p className="text-[15px] font-semibold tracking-tight text-content">
            Core<span className="text-primary">OS</span>
          </p>
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-content-subtle">
            {APP_VERSION}
          </p>
        </div>
      </div>

      <div className="px-4 pb-3">
        <Link
          href="/dashboard/ai"
          onClick={onNavigate}
          className="flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-primary text-[13px] font-semibold text-primary-fg transition-colors hover:bg-primary-bright focus-ring"
        >
          <Plus size={16} /> New Command
        </Link>
      </div>

      <nav className="custom-scrollbar flex-1 space-y-1 overflow-y-auto px-3 py-2">
        {PRIMARY_NAV.map((item) => {
          const active = isActive(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onNavigate}
              className={cn(
                "group relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-all duration-150",
                active
                  ? "bg-surface-high font-medium text-primary"
                  : "text-content-muted hover:bg-surface-raised/60 hover:text-content",
              )}
            >
              {active ? (
                <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-primary" />
              ) : null}
              <Icon size={18} className={active ? "text-primary" : ""} />
              <span>{item.label}</span>
            </Link>
          );
        })}

        <p className="px-3 pb-1 pt-5 font-mono text-[10px] uppercase tracking-[0.16em] text-content-subtle">
          Coming soon
        </p>
        {FUTURE_NAV.map((item) => {
          const Icon = item.icon;
          return (
            <div
              key={item.label}
              className="flex cursor-not-allowed items-center justify-between rounded-lg px-3 py-2.5 text-sm text-content-subtle/70"
              title="Not implemented in this MVP"
            >
              <span className="flex items-center gap-3">
                <Icon size={18} />
                {item.label}
              </span>
              <span className="rounded border border-border px-1.5 py-0.5 text-[9px] uppercase tracking-wide">
                Soon
              </span>
            </div>
          );
        })}
      </nav>

      <div className="space-y-1 border-t border-border px-3 py-3">
        <a
          href="https://code.claude.com/docs"
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-content-muted transition-colors hover:bg-surface-raised/60 hover:text-content"
        >
          <LifeBuoy size={18} /> Support
        </a>
        <button
          onClick={signOut}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-content-muted transition-colors hover:bg-danger/10 hover:text-danger focus-ring"
        >
          <LogOut size={18} /> Sign Out
        </button>
      </div>
    </div>
  );
}
