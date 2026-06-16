"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Bot,
  Calendar,
  CloudSun,
  HardDrive,
  LayoutDashboard,
  ListTodo,
  Settings,
  ShieldCheck,
  StickyNote,
  Wallet,
  Workflow,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/format";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  soon?: boolean;
}

const PRIMARY_NAV: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/dashboard/ai", label: "AI Chat", icon: Bot },
  { href: "/dashboard/tasks", label: "Tasks", icon: ListTodo },
  { href: "/dashboard/notes", label: "Notes", icon: StickyNote },
  { href: "/dashboard/finance", label: "Finance", icon: Wallet },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
];

// Shown but disabled — honest about what is not built yet (no fake modules).
const FUTURE_NAV: NavItem[] = [
  { href: "#", label: "Drive", icon: HardDrive, soon: true },
  { href: "#", label: "Calendar", icon: Calendar, soon: true },
  { href: "#", label: "Weather", icon: CloudSun, soon: true },
  { href: "#", label: "Automations", icon: Workflow, soon: true },
];

export function Sidebar() {
  const pathname = usePathname();

  const isActive = (href: string) =>
    href === "/dashboard" ? pathname === href : pathname.startsWith(href);

  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-64 flex-col border-r border-border bg-surface/80 backdrop-blur-[12px]">
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-fg">
          <ShieldCheck size={18} />
        </div>
        <div className="leading-tight">
          <p className="text-[15px] font-semibold tracking-tight text-content">CoreOS</p>
          <p className="label-mono">Command Center</p>
        </div>
      </div>

      <nav className="custom-scrollbar flex-1 space-y-1 overflow-y-auto px-3 py-2">
        {PRIMARY_NAV.map((item) => {
          const active = isActive(item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "group flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-all duration-150",
                active
                  ? "border-l-2 border-primary bg-surface-high font-medium text-primary"
                  : "border-l-2 border-transparent text-content-muted hover:translate-x-0.5 hover:bg-surface-raised/60 hover:text-content",
              )}
            >
              <Icon size={18} />
              <span>{item.label}</span>
            </Link>
          );
        })}

        <p className="px-3 pb-1 pt-5 label-mono">Coming soon</p>
        {FUTURE_NAV.map((item) => {
          const Icon = item.icon;
          return (
            <div
              key={item.label}
              className="flex cursor-not-allowed items-center justify-between gap-3 rounded-lg px-3 py-2.5 text-sm text-content-subtle/70"
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

      <div className="border-t border-border px-4 py-4">
        <p className="text-[11px] leading-relaxed text-content-subtle">
          Human approval required for write actions. AI suggestions require approval.
        </p>
      </div>
    </aside>
  );
}
