import {
  Bot,
  Brain,
  BookOpenCheck,
  Calculator,
  CalendarDays,
  ClipboardCheck,
  Clock,
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
  { href: "/dashboard/routines", label: "Routine", icon: CalendarDays },
  { href: "/dashboard/tasks", label: "Task", icon: ListTodo },
  { href: "/dashboard/finance", label: "Finance", icon: Wallet },
  { href: "/dashboard/notes", label: "Notes", icon: StickyNote },
  { href: "/dashboard/approvals", label: "Approval", icon: ClipboardCheck },
];

// Now accessible (MVP preview pages with honest setup states).
export const MODULE_NAV: NavItem[] = [
  { href: "/dashboard/calculator", label: "Calculator", icon: Calculator },
  { href: "/dashboard/clock", label: "Clock", icon: Clock },
  { href: "/dashboard/drive", label: "Drive", icon: HardDrive, badge: "MVP" },
  { href: "/dashboard/automations", label: "Automations", icon: Workflow, badge: "MVP" },
  { href: "/dashboard/ai/knowledge", label: "AI Knowledge", icon: BookOpenCheck, badge: "NEW" },
  { href: "/dashboard/ai/memory", label: "AI Memory", icon: Brain, badge: "NEW" },
];

export const SETTINGS_NAV: NavItem = { href: "/dashboard/settings", label: "Settings", icon: Settings };

export const APP_VERSION = "v4.1.0";
