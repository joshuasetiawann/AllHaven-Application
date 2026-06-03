import { cn } from "@/lib/format";

export interface Bar {
  label: string;
  value: number;
}

/** Minimal dependency-free bar chart (pure CSS). */
export function BarChart({
  data,
  height = 120,
  highlightPeak = true,
  formatValue,
  className,
}: {
  data: Bar[];
  height?: number;
  /** Glow the largest bar (the real peak) instead of always the last one. */
  highlightPeak?: boolean;
  /** When given, render a small formatted value above each non-empty bar. */
  formatValue?: (value: number) => string;
  className?: string;
}) {
  const max = Math.max(1, ...data.map((d) => d.value));
  const hasValues = data.some((d) => d.value > 0);
  return (
    <div className={cn("flex items-end gap-2", className)} style={{ height }}>
      {data.map((bar) => {
        // Floor only non-empty bars, so genuinely-zero buckets render flat
        // instead of uniform stubs that look like a static placeholder.
        const pct = bar.value > 0 ? Math.max(6, Math.round((bar.value / max) * 100)) : 0;
        const isPeak = highlightPeak && hasValues && bar.value === max;
        return (
          <div key={bar.label} className="flex flex-1 flex-col items-center justify-end gap-1.5">
            {formatValue && bar.value > 0 ? (
              <span className="text-[9.5px] font-medium tabular-nums text-content-muted">
                {formatValue(bar.value)}
              </span>
            ) : null}
            <div className="flex w-full flex-1 items-end">
              <div
                className={cn(
                  "w-full rounded-t-md transition-all duration-500",
                  isPeak ? "bg-primary shadow-glow-primary" : "bg-surface-high",
                )}
                style={{ height: `${pct}%` }}
                title={`${bar.label}: ${formatValue ? formatValue(bar.value) : bar.value}`}
              />
            </div>
            <span className="text-[10px] uppercase tracking-wide text-content-subtle">{bar.label}</span>
          </div>
        );
      })}
    </div>
  );
}
