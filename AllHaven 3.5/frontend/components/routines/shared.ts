import { Moon, Sun, Sunrise, type LucideIcon } from "lucide-react";
import type { RoutineEvent } from "@/types";

export type ViewMode = "selected" | "upcoming" | "all";
export type TimePeriod = "morning" | "afternoon" | "evening";
export type RepeatRule = "once" | "daily" | "weekly" | "monthly";

export interface RoutineForm {
  title: string;
  description: string;
  location: string;
  start_at: string;
  end_at: string;
  all_day: boolean;
  time_period: TimePeriod;
  repeat_rule: RepeatRule;
  repeat_days: string[];
}

export const PERIODS = [
  { key: "morning", label: "Morning", helper: "05:00 – 11:59", time: "07:00", Icon: Sunrise },
  { key: "afternoon", label: "Afternoon", helper: "12:00 – 16:59", time: "13:00", Icon: Sun },
  { key: "evening", label: "Evening", helper: "17:00 onwards", time: "19:00", Icon: Moon },
] as const satisfies readonly {
  key: TimePeriod;
  label: string;
  helper: string;
  time: string;
  Icon: LucideIcon;
}[];

export const DAYS = [
  { key: "mon", label: "Mon" },
  { key: "tue", label: "Tue" },
  { key: "wed", label: "Wed" },
  { key: "thu", label: "Thu" },
  { key: "fri", label: "Fri" },
  { key: "sat", label: "Sat" },
  { key: "sun", label: "Sun" },
];

export const REPEAT_OPTIONS: { key: RepeatRule; label: string }[] = [
  { key: "once", label: "Once" },
  { key: "daily", label: "Daily" },
  { key: "weekly", label: "Weekly" },
  { key: "monthly", label: "Monthly" },
];

export const emptyForm: RoutineForm = {
  title: "",
  description: "",
  location: "",
  start_at: "",
  end_at: "",
  all_day: false,
  time_period: "morning",
  repeat_rule: "daily",
  repeat_days: DAYS.map((day) => day.key),
};

export function pad(value: number): string {
  return String(value).padStart(2, "0");
}

export function dateKey(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function startOfLocalDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

export function addDays(date: Date, days: number): Date {
  const next = new Date(date);
  next.setDate(next.getDate() + days);
  return next;
}

export function isoToLocalInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function periodFromHour(hour: number): TimePeriod {
  if (hour >= 5 && hour < 12) return "morning";
  if (hour >= 12 && hour < 17) return "afternoon";
  return "evening";
}

export function periodFromRoutine(routine: RoutineEvent): TimePeriod {
  if (
    routine.time_period === "morning" ||
    routine.time_period === "afternoon" ||
    routine.time_period === "evening"
  ) {
    return routine.time_period;
  }
  return periodFromHour(new Date(routine.start_at).getHours());
}

export function defaultStartFor(dateValue: string, period: TimePeriod): string {
  const time = PERIODS.find((item) => item.key === period)?.time ?? "07:00";
  return `${dateValue}T${time}`;
}

export function setTimeOnInput(value: string, dateValue: string, time: string): string {
  const date = value ? value.slice(0, 10) : dateValue;
  return `${date}T${time}`;
}

export function formatLongDay(key: string): string {
  return new Date(`${key}T00:00:00`).toLocaleDateString("en-US", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

export function formatShortDay(date: Date): string {
  return date.toLocaleDateString("en-US", { weekday: "short", day: "numeric", month: "short" });
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
}

export function weekdayShort(date: Date): string {
  return date.toLocaleDateString("en-US", { weekday: "short" });
}

export function eventDayKey(event: RoutineEvent): string {
  return dateKey(new Date(event.start_at));
}

export function eventStatus(event: RoutineEvent): "past" | "now" | "upcoming" {
  const now = Date.now();
  const startDate = new Date(event.start_at);
  if (event.all_day) {
    const start = startOfLocalDay(startDate).getTime();
    const end = addDays(startOfLocalDay(startDate), 1).getTime() - 1;
    if (end < now) return "past";
    if (start <= now && now <= end) return "now";
    return "upcoming";
  }
  const start = startDate.getTime();
  const end = event.end_at ? new Date(event.end_at).getTime() : start;
  if (end < now) return "past";
  if (start <= now && now <= end) return "now";
  return "upcoming";
}

export function repeatLabel(routine: RoutineEvent): string {
  const rule = routine.repeat_rule ?? "once";
  if (rule === "daily") return "Daily";
  if (rule === "weekly") return "Weekly";
  if (rule === "monthly") return "Monthly";
  return "Once";
}
