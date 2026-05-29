// Chat "sections" — each module the AI chat can carry a separate, local memory
// for. A section is just a stable key + a human label + a short hint describing
// what context that section cares about. The hint is shown to the user and used
// to steer the AI when its section memory is injected into a prompt.

import {
  Bot,
  Calendar,
  CloudSun,
  FolderGit2,
  HardDrive,
  ListTodo,
  Settings,
  SlidersHorizontal,
  StickyNote,
  Wallet,
  Workflow,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ChatGroup } from "@/types";

export interface SectionDef {
  key: string;
  label: string;
  icon: LucideIcon;
  /** What this section is about — guides the AI and is shown to the user. */
  hint: string;
}

export const SECTIONS: SectionDef[] = [
  { key: "general", label: "General", icon: Bot, hint: "Open-ended assistant — no module focus." },
  { key: "tasks", label: "Tasks", icon: ListTodo, hint: "Planning, priorities, and to-dos." },
  { key: "notes", label: "Notes", icon: StickyNote, hint: "Writing, knowledge, and references." },
  { key: "finance", label: "Finance", icon: Wallet, hint: "Cashflow, budgets, and money tracking." },
  { key: "calendar", label: "Calendar", icon: Calendar, hint: "Events, scheduling, and time." },
  { key: "drive", label: "Files", icon: HardDrive, hint: "Documents and file organization." },
  { key: "automations", label: "Automations", icon: Workflow, hint: "Workflows and automation ideas." },
  { key: "weather", label: "Weather", icon: CloudSun, hint: "Locations and weather context." },
  { key: "settings", label: "Settings", icon: Settings, hint: "App configuration and providers." },
  { key: "system", label: "System Control", icon: SlidersHorizontal, hint: "Services, status, and operations." },
];

export const DEFAULT_SECTION_KEY = "general";

const BY_KEY: Record<string, SectionDef> = Object.fromEntries(SECTIONS.map((s) => [s.key, s]));

export function sectionByKey(key: string | null | undefined): SectionDef {
  return (key && BY_KEY[key]) || BY_KEY[DEFAULT_SECTION_KEY];
}

/** Map a dashboard route to the section it belongs to (for auto-suggesting). */
export function sectionFromPath(pathname: string): SectionDef {
  const seg = pathname.replace(/^\/dashboard\/?/, "").split("/")[0] || "";
  if (seg === "ai" || seg === "") return sectionByKey("general");
  if (seg === "settings" && pathname.includes("/system")) return sectionByKey("system");
  return sectionByKey(seg);
}

// --- project/group sections -------------------------------------------------
// A chat group/project carries its own memory under the key `project:<groupId>`.

const PROJECT_PREFIX = "project:";

export function projectSectionKey(groupId: string): string {
  return `${PROJECT_PREFIX}${groupId}`;
}

export function isProjectSection(key: string): boolean {
  return key.startsWith(PROJECT_PREFIX);
}

export function projectIdOf(key: string): string | null {
  return isProjectSection(key) ? key.slice(PROJECT_PREFIX.length) : null;
}

/**
 * Resolve any section key — module OR `project:<id>` — to a display def,
 * pulling the live group name (and a folder icon) for project sections.
 */
export function resolveSection(key: string, groups: ChatGroup[] = []): SectionDef {
  if (isProjectSection(key)) {
    const id = projectIdOf(key);
    const group = groups.find((g) => g.id === id);
    return {
      key,
      label: group ? group.name : "Project",
      icon: FolderGit2,
      hint: "Memory for this chat group / project.",
    };
  }
  return sectionByKey(key);
}
