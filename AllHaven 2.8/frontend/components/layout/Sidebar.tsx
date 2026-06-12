"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
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
          "group relative flex items-center gap-3 rounded-lg py-2.5 text-sm transition-all duration-150 focus-ring",
          collapsed ? "justify-center px-0" : "justify-between px-3",
          active
            ? "bg-surface-high font-medium text-primary"
            : "text-content-muted hover:bg-surface-raised/60 hover:text-content",
        )}
      >
        {active ? (
          <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-primary" />
        ) : null}
        <span className={cn("flex min-w-0 items-center gap-3", collapsed && "gap-0")}>
          <Icon size={18} className={cn("shrink-0", active ? "text-primary" : "")} />
          {collapsed ? null : <span className="truncate">{item.label}</span>}
        </span>
        {item.badge && !collapsed ? (
          <span className="shrink-0 rounded border border-border px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-content-subtle">
            {item.badge}
          </span>
        ) : null}
      </Link>
    );
  };

  return (
    <div
      className={cn(
        "flex h-full flex-col border-r border-border bg-bg-deep/95 transition-[width] duration-200 ease-out",
        collapsed ? "w-[76px]" : "w-[260px]",
      )}
    >
      <div
        className={cn(
          "flex items-center py-5",
          collapsed ? "justify-center px-0" : "gap-2.5 px-5",
        )}
      >
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-fg shadow-glow-primary">
          <ShieldCheck size={18} />
        </div>
        {collapsed ? null : (
          <div className="leading-tight">
            <p className="text-[15px] font-semibold tracking-tight text-content">
              All<span className="text-primary">Haven</span>
            </p>
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-content-subtle">
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
            "flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-primary text-[13px] font-semibold text-primary-fg transition-colors hover:bg-primary-bright focus-ring",
          )}
        >
          <Plus size={16} className="shrink-0" />
          {collapsed ? null : "New Command"}
        </Link>
      </div>

      <nav className="custom-scrollbar flex-1 space-y-1 overflow-y-auto overflow-x-hidden px-3 py-2">
        {PRIMARY_NAV.map(renderItem)}

        {collapsed ? (
          <div className="mx-3 my-3 h-px bg-border" />
        ) : (
          <p className="px-3 pb-1 pt-5 font-mono text-[10px] uppercase tracking-[0.16em] text-content-subtle">
            Modules
          </p>
        )}
        {MODULE_NAV.map(renderItem)}

        <div className="my-2 h-px bg-border" />
        {renderItem(SETTINGS_NAV)}
      </nav>

      <div className={cn("space-y-1 border-t border-border py-3", collapsed ? "px-3" : "px-3")}>
        {user ? (
          <div
            className={cn(
              "flex items-center rounded-lg py-1.5",
              collapsed ? "justify-center px-0" : "gap-2.5 px-2",
            )}
            title={collapsed ? user.full_name || user.email : undefined}
          >
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-primary/30 bg-primary/10 text-[12px] font-semibold text-primary">
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
            "flex items-center gap-3 rounded-lg py-2 text-sm text-content-muted transition-colors hover:bg-surface-raised/60 hover:text-content focus-ring",
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
            "flex w-full items-center gap-3 rounded-lg py-2 text-sm text-content-muted transition-colors hover:bg-danger/10 hover:text-danger focus-ring",
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
              "flex w-full items-center gap-3 rounded-lg py-2 text-sm text-content-muted transition-colors hover:bg-surface-raised/60 hover:text-content focus-ring",
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
