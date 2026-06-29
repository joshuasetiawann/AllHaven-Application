import { Search } from "lucide-react";
import { cn } from "@/lib/format";
import type { ViewMode } from "./shared";

const FILTERS: { key: ViewMode; label: string }[] = [
  { key: "selected", label: "Today" },
  { key: "upcoming", label: "Upcoming" },
  { key: "all", label: "All" },
];

/** Toolbar: segmented view filters on the left, search + date picker on the right. */
export function RoutineToolbar({
  view,
  onView,
  query,
  onQuery,
  date,
  onDate,
  todayKey,
}: {
  view: ViewMode;
  onView: (view: ViewMode) => void;
  query: string;
  onQuery: (value: string) => void;
  date: string;
  onDate: (value: string) => void;
  todayKey: string;
}) {
  return (
    <div className="panel flex flex-col gap-3 p-3 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex items-center gap-1 rounded-md border border-border bg-surface-input/50 p-[3px]">
        {FILTERS.map((filter) => {
          const active = view === filter.key;
          return (
            <button
              key={filter.key}
              onClick={() => onView(filter.key)}
              aria-pressed={active}
              className={cn(
                "h-8 rounded-[9px] border px-3 text-[13px] font-medium transition-colors focus-ring",
                active
                  ? "border-primary/30 bg-[linear-gradient(90deg,rgb(var(--color-primary)/0.20),rgb(var(--color-secondary)/0.12))] text-content shadow-glow-primary"
                  : "border-transparent text-content-muted hover:text-content",
              )}
            >
              {filter.label}
            </button>
          );
        })}
      </div>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <div className="relative sm:w-64">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-content-subtle" />
          <input
            value={query}
            onChange={(event) => onQuery(event.target.value)}
            placeholder="Search routines..."
            className="h-9 w-full rounded-md border border-border bg-surface-input pl-9 pr-3 text-sm text-content placeholder:text-content-subtle focus:border-primary/70 focus:outline-none focus:ring-1 focus:ring-primary/30"
          />
        </div>
        <input
          type="date"
          value={date}
          onChange={(event) => onDate(event.target.value || todayKey)}
          aria-label="Pick a date"
          className="h-9 rounded-md border border-border bg-surface-input px-3 font-mono text-[13px] text-content focus:border-primary/70 focus:outline-none focus:ring-1 focus:ring-primary/30 sm:w-44"
        />
      </div>
    </div>
  );
}
