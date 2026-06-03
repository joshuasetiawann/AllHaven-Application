"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ChevronDown,
  ChevronsLeft,
  ChevronsRight,
  LogOut,
  LifeBuoy,
  Plus,
  ShieldCheck,
} from "lucide-react";
import { APP_VERSION, MODULE_NAV, PRIMARY_NAV, SETTINGS_NAV } from "@/components/layout/nav";
import type { NavItem } from "@/components/layout/nav";
import { authApi } from "@/lib/api";
import { clearAuth, getStoredUser } from "@/lib/auth";
import { cn, initials } from "@/lib/format";

export function Sidebar({
  pathname,
  onNavigate,
  collapsed = false,
  canToggle = false,
  onToggleCollapse,
}: {
  pathname: string;
  onNavigate?: () => void;
  collapsed?: boolean;
  canToggle?: boolean;
  onToggleCollapse?: () => void;
}) {
  const router = useRouter();
  const user = getStoredUser();
  // Mobile drawer only: keep the secondary "Modules" group collapsed so the drawer
  // isn't a wall of 14 links. Always expanded on desktop (md+) via `md:block`.
  const [showModules, setShowModules] = useState(false);

  // Collect every href in the nav so we can detect a more-specific match.
  const allHrefs = [
    ...PRIMARY_NAV.map((i) => i.href),
    ...MODULE_NAV.map((i) => i.href),
    SETTINGS_NAV.href,
  ];

  const isActive = (href: string) => {
    // Dashboard root must be an exact match — it is a prefix of every other route.
    if (href === "/dashboard") return pathname === "/dashboard";
    // Basic prefix match: equal or a sub-path.
    const prefixMatch = pathname === href || pathname.startsWith(href + "/");
    if (!prefixMatch) return false;
    // Longest-prefix wins: deactivate this item if any other nav href is a
    // longer, more-specific match for the current pathname.
    const hasMoreSpecific = allHrefs.some(
      (other) =>
        other !== href &&
        other.startsWith(href + "/") &&
        (pathname === other || pathname.startsWith(other + "/")),
    );
    return !hasMoreSpecific;
  };

  const signOut = async () => {
    // Revoke the server-side session + clear cookies, then drop the local cache.
    await authApi.logout().catch(() => {});
    clearAuth();
    router.replace("/login");
  };

  const renderItem = (item: NavItem) => {
    const active = isActive(item.href);
    const Icon = item.icon;
    return (
      <Link
        key={item.href}
        href={item.href}
        onClick={onNavigate}
        aria-current={active ? "page" : undefined}
        title={collapsed ? item.label : undefined}
        className={cn(
          "group relative flex min-h-[44px] items-center gap-3 rounded-lg border py-2 text-sm transition-all duration-200 focus-ring",
          collapsed ? "justify-center px-0" : "justify-between px-3",
          active
            ? "border-primary/30 bg-[linear-gradient(90deg,rgb(var(--color-primary)/0.18),rgb(var(--color-secondary)/0.10))] font-semibold text-content shadow-glow-primary"
            : "border-transparent text-content-muted hover:border-white/[0.06] hover:bg-white/[0.04] hover:text-content",
        )}
      >
        <span className={cn("flex min-w-0 items-center gap-3", collapsed && "gap-0")}>
          <span
            className={cn(
              "flex h-8 w-8 shrink-0 items-center justify-center rounded-[10px] border transition-colors",
              active
                ? "grad-primary border-transparent text-primary-fg"
                : "border-white/[0.08] bg-white/[0.035] text-content-muted group-hover:border-border-strong group-hover:text-content",
            )}
          >
            <Icon size={17} />
          </span>
          {collapsed ? null : <span className="truncate">{item.label}</span>}
        </span>
        {item.badge && !collapsed ? (
          <span
            className={cn(
              "shrink-0 rounded-full border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wide",
              item.badge === "NEW"
                ? "border-primary/30 bg-primary/10 text-primary-bright"
                : "border-border bg-surface-input px-1.5 text-content-subtle",
            )}
          >
            {item.badge}
          </span>
        ) : null}
      </Link>
    );
  };

  return (
    <div
      className={cn(
        "flex h-full flex-col border-r border-white/[0.07] bg-[linear-gradient(180deg,rgba(14,16,30,0.72),rgba(8,9,16,0.72))] backdrop-blur-[18px] transition-[width] duration-200 ease-out",
        collapsed ? "w-[80px]" : "w-[280px]",
      )}
    >
      <div
        className={cn(
          "flex items-center py-5",
          collapsed ? "justify-center px-0" : "gap-3 px-5",
        )}
      >
        <div className="grad-primary flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-lg text-primary-fg shadow-[0_0_28px_rgb(var(--color-primary)/0.5)]">
          <ShieldCheck size={19} />
        </div>
        {collapsed ? null : (
          <div className="min-w-0 leading-tight">
            <p className="text-[16px] font-semibold tracking-[-0.01em] text-content">
              All<span className="text-grad">Haven</span>
            </p>
            <p className="mt-[3px] font-mono text-[10px] uppercase tracking-[0.2em] text-content-faint">
              {APP_VERSION}
            </p>
          </div>
        )}
      </div>

      <div className={cn("pb-3", collapsed ? "px-3" : "px-4")}>
        <Link
          href="/dashboard/tasks"
          onClick={onNavigate}
          title={collapsed ? "New Command" : undefined}
          className={cn(
            "grad-primary flex h-[46px] w-full items-center justify-center gap-2 rounded-lg text-[13px] font-semibold text-primary-fg shadow-btn-primary transition-all duration-200 hover:brightness-[1.06] focus-ring",
          )}
        >
          <Plus size={16} className="shrink-0" />
          {collapsed ? null : "New Command"}
        </Link>
      </div>

      <nav className="custom-scrollbar flex-1 space-y-1 overflow-y-auto overflow-x-hidden px-3 py-2">
        {collapsed ? null : (
          <p className="px-3 pb-1 font-mono text-[10px] uppercase tracking-[0.18em] text-content-faint">
            Workspace
          </p>
        )}
        {PRIMARY_NAV.map(renderItem)}

        {collapsed ? (
          <div className="mx-3 my-3 h-px bg-white/[0.07]" />
        ) : (
          <button
            type="button"
            onClick={() => setShowModules((v) => !v)}
            className="flex w-full items-center justify-between px-3 pb-1 pt-5 font-mono text-[10px] uppercase tracking-[0.18em] text-content-faint md:pointer-events-none"
          >
            Modules
            <ChevronDown
              size={12}
              className={cn("shrink-0 transition-transform md:hidden", showModules && "rotate-180")}
            />
          </button>
        )}
        <div className={cn("space-y-1", showModules ? "block" : "hidden", "md:block")}>
          {MODULE_NAV.map(renderItem)}
        </div>

        <div className="my-2 h-px bg-white/[0.07]" />
        {renderItem(SETTINGS_NAV)}
      </nav>

      <div className={cn("space-y-1 border-t border-white/[0.07] py-3", collapsed ? "px-3" : "px-3")}>
        {user ? (
          <div
            className={cn(
              "glass-tile flex items-center py-2",
              collapsed ? "justify-center px-0" : "gap-2.5 px-2.5",
            )}
            title={collapsed ? user.full_name || user.email : undefined}
          >
            <span className="grad-primary flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[12px] font-semibold text-primary-fg">
              {initials(user.full_name || user.email)}
            </span>
            {collapsed ? null : (
              <div className="min-w-0 leading-tight">
                {user.full_name ? (
                  <p className="truncate text-[13px] font-medium text-content">{user.full_name}</p>
                ) : null}
                <p className="truncate text-[11px] text-content-subtle">{user.email}</p>
              </div>
            )}
          </div>
        ) : null}

        <a
          href="https://code.claude.com/docs"
          target="_blank"
          rel="noreferrer"
          title={collapsed ? "Support" : undefined}
          className={cn(
            "flex items-center gap-3 rounded-xl py-2 text-sm text-content-muted transition-colors hover:bg-surface-raised/60 hover:text-content focus-ring",
            collapsed ? "justify-center px-0" : "px-3",
          )}
        >
          <LifeBuoy size={18} className="shrink-0" />
          {collapsed ? null : "Support"}
        </a>
        <button
          onClick={signOut}
          title={collapsed ? "Sign Out" : undefined}
          className={cn(
            "flex w-full items-center gap-3 rounded-xl py-2 text-sm text-content-muted transition-colors hover:bg-danger/10 hover:text-danger focus-ring",
            collapsed ? "justify-center px-0" : "px-3",
          )}
        >
          <LogOut size={18} className="shrink-0" />
          {collapsed ? null : "Sign Out"}
        </button>

        {canToggle && onToggleCollapse ? (
          <button
            onClick={onToggleCollapse}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className={cn(
              "flex w-full items-center gap-3 rounded-xl py-2 text-sm text-content-muted transition-colors hover:bg-surface-raised/60 hover:text-content focus-ring",
              collapsed ? "justify-center px-0" : "px-3",
            )}
          >
            {collapsed ? (
              <ChevronsRight size={18} className="shrink-0" />
            ) : (
              <ChevronsLeft size={18} className="shrink-0" />
            )}
            {collapsed ? null : "Collapse"}
          </button>
        ) : null}
      </div>
    </div>
  );
}
