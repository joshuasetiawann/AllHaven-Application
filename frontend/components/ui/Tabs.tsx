import { cn } from "@/lib/format";

export interface TabItem {
  value: string;
  label: string;
  count?: number;
}

export function Tabs({
  items,
  value,
  onChange,
  className,
}: {
  items: TabItem[];
  value: string;
  onChange: (value: string) => void;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "custom-scrollbar flex max-w-full overflow-x-auto rounded-md border border-border bg-surface-input/60 p-[3px]",
        className,
      )}
    >
      {items.map((item) => {
        const active = item.value === value;
        return (
          <button
            key={item.value}
            onClick={() => onChange(item.value)}
            className={cn(
              "inline-flex shrink-0 items-center gap-1.5 rounded-sm border px-3 py-1.5 text-[12.5px] transition-colors focus-ring",
              active
                ? "border-primary/30 bg-[linear-gradient(90deg,rgb(var(--color-primary)/0.2),rgb(var(--color-secondary)/0.12))] font-semibold text-content"
                : "border-transparent text-content-muted hover:text-content",
            )}
          >
            {item.label}
            {typeof item.count === "number" ? (
              <span
                className={cn(
                  "rounded-full px-1.5 text-[11px]",
                  active ? "bg-primary/15 text-primary-bright" : "bg-surface-high text-content-subtle",
                )}
              >
                {item.count}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
