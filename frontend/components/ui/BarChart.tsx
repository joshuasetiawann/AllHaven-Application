import { cn } from "@/lib/format";

export interface Bar {
  label: string;
  value: number;
}

/** Minimal dependency-free bar chart (pure CSS). */
export function BarChart({
  data,
  height = 120,
  highlightLast = true,
  className,
}: {
  data: Bar[];
  height?: number;
  highlightLast?: boolean;
  className?: string;
}) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <div className={cn("flex items-end gap-2", className)} style={{ height }}>
      {data.map((bar, index) => {
        const pct = Math.max(4, Math.round((bar.value / max) * 100));
        const isLast = highlightLast && index === data.length - 1;
        return (
          <div key={bar.label} className="flex flex-1 flex-col items-center justify-end gap-2">
            <div className="flex w-full flex-1 items-end">
              <div
                className={cn(
                  "w-full rounded-t-md transition-all duration-500",
                  isLast ? "bg-primary shadow-glow-primary" : "bg-surface-high",
                )}
                style={{ height: `${pct}%` }}
                title={`${bar.label}: ${bar.value}`}
              />
            </div>
            <span className="text-[10px] uppercase tracking-wide text-content-subtle">{bar.label}</span>
          </div>
        );
      })}
    </div>
  );
}
