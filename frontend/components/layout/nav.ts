import {
  Bot,
  Calculator,
  Calendar,
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
}

export const PRIMARY_NAV: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/dashboard/ai", label: "AI Chat", icon: Bot },
  { href: "/dashboard/tasks", label: "Tasks", icon: ListTodo },
  { href: "/dashboard/notes", label: "Notes", icon: StickyNote },
  { href: "/dashboard/finance", label: "Finance", icon: Wallet },
];

// Now accessible (MVP preview pages with honest setup states).
export const MODULE_NAV: NavItem[] = [
  { href: "/dashboard/calculator", label: "Calculator", icon: Calculator },
  { href: "/dashboard/clock", label: "Clock", icon: Clock },
  { href: "/dashboard/drive", label: "Drive", icon: HardDrive, badge: "MVP" },
  { href: "/dashboard/calendar", label: "Calendar", icon: Calendar, badge: "MVP" },
  { href: "/dashboard/weather", label: "Weather", icon: CloudSun, badge: "MVP" },
  { href: "/dashboard/automations", label: "Automations", icon: Workflow, badge: "MVP" },
];

export const SETTINGS_NAV: NavItem = { href: "/dashboard/settings", label: "Settings", icon: Settings };

export const APP_VERSION = "v0.12.0";
