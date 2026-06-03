"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/format";

export interface Bar {
  label: string;
  value: number;
}

/** Minimal dependency-free bar chart (pure CSS) with a grow-in animation. */
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
  // Grow the bars up from the baseline on mount and whenever the data changes,
  // so the chart visibly "moves" instead of looking like a static placeholder.
  const [grown, setGrown] = useState(false);
  const signature = data.map((d) => `${d.label}:${d.value}`).join("|");
  useEffect(() => {
    setGrown(false);
    const t = setTimeout(() => setGrown(true), 40);
    return () => clearTimeout(t);
  }, [signature]);

  const max = Math.max(1, ...data.map((d) => d.value));
  const hasValues = data.some((d) => d.value > 0);
  return (
    <div className={cn("relative flex gap-2", className)} style={{ height }}>
      <div className="pointer-events-none absolute inset-x-0 bottom-5 border-t border-border/80" />
      {data.map((bar, index) => {
        // Floor only non-empty bars, so genuinely-zero buckets render flat
        // instead of uniform stubs that look like a static placeholder.
        const pct = bar.value > 0 ? Math.max(6, Math.round((bar.value / max) * 100)) : 0;
        const isPeak = highlightPeak && hasValues && bar.value === max;
        return (
          <div key={bar.label} className="relative flex h-full min-w-0 flex-1 flex-col items-center justify-end gap-1.5">
            {formatValue && bar.value > 0 ? (
              <span
                className={cn(
                  "text-[9.5px] font-medium tabular-nums text-content-muted transition-opacity duration-500",
                  grown ? "opacity-100" : "opacity-0",
                )}
              >
                {formatValue(bar.value)}
              </span>
            ) : null}
            <div className="flex min-h-0 w-full flex-1 items-end">
              <div
                className={cn(
                  "min-h-0 w-full rounded-t-md transition-[height] duration-700 ease-out",
                  bar.value > 0
                    ? isPeak
                      ? "bg-primary shadow-glow-primary"
                      : "bg-primary/45"
                    : "bg-transparent",
                )}
                style={{
                  height: grown ? `${pct}%` : "0%",
                  transitionDelay: `${index * 45}ms`,
                }}
                title={`${bar.label}: ${formatValue ? formatValue(bar.value) : bar.value}`}
              />
            </div>
            <span className="text-[10px] uppercase tracking-wide text-content-subtle">{bar.label}</span>
          </div>
        );
      })}
      {!hasValues ? (
        <div className="pointer-events-none absolute inset-x-0 top-1/2 -translate-y-1/2 text-center text-[11px] text-content-subtle">
          No activity in this period
        </div>
      ) : null}
    </div>
  );
}
