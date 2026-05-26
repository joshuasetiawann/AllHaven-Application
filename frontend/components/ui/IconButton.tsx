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
        "inline-flex h-9 w-9 items-center justify-center rounded-md border transition-colors focus-ring",
        active
          ? "border-primary/40 bg-primary/10 text-primary"
          : "border-border bg-surface/40 text-content-muted hover:border-border-strong hover:text-content",
        className,
      )}
      {...props}
    />
  ),
);

IconButton.displayName = "IconButton";
