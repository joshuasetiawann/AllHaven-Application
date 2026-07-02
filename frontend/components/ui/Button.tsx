import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/format";

type Variant = "primary" | "ghost" | "danger" | "subtle";
type Size = "sm" | "md";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
}

const variants: Record<Variant, string> = {
  // Solid electric-cyan with dark text — the surgical primary action.
  primary:
    "bg-primary text-primary-fg font-semibold hover:bg-primary-dim disabled:opacity-50",
  // Transparent with hairline border; cyan text on hover.
  ghost:
    "border border-border text-content hover:text-primary hover:border-primary/60 disabled:opacity-50",
  danger:
    "border border-danger/40 text-danger hover:bg-danger/10 disabled:opacity-50",
  subtle:
    "bg-surface-high text-content hover:bg-surface-raised disabled:opacity-50",
};

const sizes: Record<Size, string> = {
  sm: "h-8 px-3 text-[13px]",
  md: "h-10 px-4 text-sm",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "primary", size = "md", className, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-md font-medium",
        "transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-primary/40",
        "disabled:cursor-not-allowed",
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  ),
);

Button.displayName = "Button";
