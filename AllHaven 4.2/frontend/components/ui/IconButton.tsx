import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/format";

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean;
}

export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  ({ active = false, className, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex h-9 w-9 items-center justify-center rounded-md border transition-all duration-200 focus-ring",
        active
          ? "border-primary/40 bg-primary/10 text-primary-bright shadow-[0_0_18px_rgb(var(--color-primary)/0.2)]"
          : "border-border bg-surface-input/45 text-content-muted hover:border-primary/35 hover:bg-surface-raised/70 hover:text-content",
        className,
      )}
      {...props}
    />
  ),
);

IconButton.displayName = "IconButton";
