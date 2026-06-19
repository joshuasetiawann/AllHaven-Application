import {
  Bot,
  Brain,
  BookOpenCheck,
  Calculator,
  CalendarDays,
  ClipboardCheck,
  Clock,
  CloudSun,
  HardDrive,
  LayoutDashboard,
  ListTodo,
  Settings,
  StickyNote,
  Wallet,
  Workflow,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  badge?: string;
  // Needs the AllHaven backend (REST). The mobile build (Supabase-only) has no
  // offline/Supabase path for these, so they're hidden + route-guarded there.
  restOnly?: boolean;
}

// The mobile APK is built with NEXT_PUBLIC_DATA_MODE=supabase. On that build the
// REST-only features have nothing to talk to, so we hide them rather than show
// dead buttons that fail against an unreachable backend.
export const IS_MOBILE = process.env.NEXT_PUBLIC_DATA_MODE === "supabase";

const PRIMARY_NAV_ALL: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/dashboard/ai", label: "AI Chat", icon: Bot, restOnly: true },
  { href: "/dashboard/routines", label: "Routine", icon: CalendarDays },
  { href: "/dashboard/tasks", label: "Task", icon: ListTodo },
  { href: "/dashboard/finance", label: "Finance", icon: Wallet },
  { href: "/dashboard/notes", label: "Notes", icon: StickyNote },
  { href: "/dashboard/approvals", label: "Approval", icon: ClipboardCheck, restOnly: true },
];

// Now accessible (MVP preview pages with honest setup states).
const MODULE_NAV_ALL: NavItem[] = [
  { href: "/dashboard/calculator", label: "Calculator", icon: Calculator },
  { href: "/dashboard/clock", label: "Clock", icon: Clock },
  { href: "/dashboard/drive", label: "Drive", icon: HardDrive, badge: "MVP", restOnly: true },
  { href: "/dashboard/weather", label: "Weather", icon: CloudSun, badge: "MVP" },
  { href: "/dashboard/automations", label: "Automations", icon: Workflow, badge: "MVP" },
  { href: "/dashboard/ai/knowledge", label: "AI Knowledge", icon: BookOpenCheck, badge: "NEW", restOnly: true },
  { href: "/dashboard/ai/memory", label: "AI Memory", icon: Brain, badge: "NEW", restOnly: true },
];

const SETTINGS_NAV_ITEM: NavItem = {
  href: "/dashboard/settings",
  label: "Settings",
  icon: Settings,
  restOnly: true,
};

const keepForBuild = (items: NavItem[]): NavItem[] =>
  IS_MOBILE ? items.filter((i) => !i.restOnly) : items;

export const PRIMARY_NAV: NavItem[] = keepForBuild(PRIMARY_NAV_ALL);
export const MODULE_NAV: NavItem[] = keepForBuild(MODULE_NAV_ALL);
// null on mobile so the Sidebar omits the Settings entry entirely.
export const SETTINGS_NAV: NavItem | null = IS_MOBILE ? null : SETTINGS_NAV_ITEM;

// Backend-only routes — used to redirect deep-links away on the mobile build.
export const REST_ONLY_HREFS: string[] = [...PRIMARY_NAV_ALL, ...MODULE_NAV_ALL, SETTINGS_NAV_ITEM]
  .filter((i) => i.restOnly)
  .map((i) => i.href);

export const APP_VERSION = "v3.7.0";
