import type { ReactNode } from "react";
import { cn } from "@/lib/format";

type Tone = "neutral" | "primary" | "secondary" | "success" | "warning" | "danger" | "info";

const tones: Record<Tone, string> = {
  neutral: "border-border bg-surface-high/70 text-content-muted",
  primary: "border-primary/30 bg-primary/10 text-primary-bright",
  secondary: "border-secondary/30 bg-secondary/12 text-secondary-soft",
  success: "border-success/30 bg-success/10 text-success-soft",
  warning: "border-warning/30 bg-warning/10 text-warning",
  danger: "border-danger/30 bg-danger/10 text-danger",
  info: "border-info/30 bg-info/10 text-info",
};

export function Badge({
  children,
  tone = "neutral",
  className,
  dot = false,
}: {
  children: ReactNode;
  tone?: Tone;
  className?: string;
  dot?: boolean;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-medium",
        tones[tone],
        className,
      )}
    >
      {dot ? <span className="h-1.5 w-1.5 rounded-full bg-current" /> : null}
      {children}
    </span>
  );
}
