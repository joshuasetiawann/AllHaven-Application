import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/format";
import { dateKey, weekdayShort } from "./shared";

/**
 * Compact rounded date cards (not big circles). The active day gets a soft
 * highlight + a thin primary ring/glow; days with routines show a small dot
 * instead of an "empty"/count label.
 */
export function DateStrip({
  days,
  selectedDate,
  isActive,
  countFor,
  onSelect,
  onShift,
}: {
  days: Date[];
  selectedDate: string;
  isActive: boolean;
  countFor: (key: string) => number;
  onSelect: (key: string) => void;
  onShift: (delta: number) => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <button
        onClick={() => onShift(-1)}
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-input text-content-muted transition-colors hover:border-border-strong hover:text-content focus-ring"
        aria-label="Previous day"
      >
        <ChevronLeft size={16} />
      </button>

      <div className="custom-scrollbar flex min-w-0 flex-1 gap-2 overflow-x-auto pb-1">
        {days.map((day) => {
          const key = dateKey(day);
          const count = countFor(key);
          const active = selectedDate === key && isActive;
          return (
            <button
              key={key}
              onClick={() => onSelect(key)}
              aria-pressed={active}
              className={cn(
                "group relative flex min-w-[4.25rem] flex-col items-center gap-0.5 rounded-xl border px-3 py-2.5 transition-all duration-200 focus-ring",
                active
                  ? "border-primary/40 bg-primary/10 text-content shadow-glow-primary ring-1 ring-primary/40"
                  : "border-border bg-surface-input/50 text-content-muted hover:border-border-strong hover:bg-surface-raised/70 hover:text-content",
              )}
            >
              <span className={cn("text-[11px] uppercase tracking-wide", active ? "text-primary" : "")}>
                {weekdayShort(day)}
              </span>
              <span className="text-base font-semibold leading-none">{day.getDate()}</span>
              <span
                aria-hidden
                className={cn(
                  "mt-1 h-1.5 w-1.5 rounded-full transition-colors",
                  count ? (active ? "bg-primary" : "bg-primary/60") : "bg-transparent",
                )}
              />
            </button>
          );
        })}
      </div>

      <button
        onClick={() => onShift(1)}
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border bg-surface-input text-content-muted transition-colors hover:border-border-strong hover:text-content focus-ring"
        aria-label="Next day"
      >
        <ChevronRight size={16} />
      </button>
    </div>
  );
}
