import {
  Bot,
  Calendar,
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
  soon?: boolean;
}

export const PRIMARY_NAV: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/dashboard/ai", label: "AI Chat", icon: Bot },
  { href: "/dashboard/tasks", label: "Tasks", icon: ListTodo },
  { href: "/dashboard/notes", label: "Notes", icon: StickyNote },
  { href: "/dashboard/finance", label: "Finance", icon: Wallet },
  { href: "/dashboard/settings", label: "Settings", icon: Settings },
];

// Visible but disabled — honest about what is not built in this MVP.
export const FUTURE_NAV: NavItem[] = [
  { href: "#", label: "Drive", icon: HardDrive, soon: true },
  { href: "#", label: "Calendar", icon: Calendar, soon: true },
  { href: "#", label: "Weather", icon: CloudSun, soon: true },
  { href: "#", label: "Automations", icon: Workflow, soon: true },
];

export const APP_VERSION = "v1.0.4-stable";
