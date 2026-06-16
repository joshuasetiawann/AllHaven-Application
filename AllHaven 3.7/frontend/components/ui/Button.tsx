import { forwardRef } from "react";
import type { ButtonHTMLAttributes } from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/format";

type Variant = "primary" | "ghost" | "danger" | "subtle" | "secondary";
type Size = "sm" | "md" | "lg" | "icon";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

const variants: Record<Variant, string> = {
  primary:
    "bg-primary text-primary-fg font-semibold shadow-[0_0_0_1px_rgba(24,224,214,0.18),0_10px_26px_-18px_rgba(24,224,214,0.9)] hover:bg-primary-bright hover:shadow-glow-primary",
  secondary:
    "border border-secondary/30 bg-secondary/15 text-secondary-soft hover:border-secondary/45 hover:bg-secondary/25",
  ghost:
    "border border-border bg-surface-input/40 text-content hover:border-primary/50 hover:bg-surface-raised/70 hover:text-primary",
  danger: "border border-danger/40 bg-danger/5 text-danger hover:bg-danger/10",
  subtle: "border border-border/60 bg-surface-high text-content hover:border-border-strong hover:bg-surface-raised",
};

const sizes: Record<Size, string> = {
  sm: "h-8 px-3 text-[13px] gap-1.5",
  md: "h-10 px-4 text-sm gap-2",
  lg: "h-11 px-5 text-[15px] gap-2",
  icon: "h-9 w-9",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "primary", size = "md", loading = false, className, children, disabled, ...props }, ref) => (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        "inline-flex select-none items-center justify-center rounded-lg font-medium",
        "transition-all duration-200 focus-ring",
        "disabled:cursor-not-allowed disabled:opacity-50",
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    >
      {loading ? <Loader2 size={size === "sm" ? 14 : 16} className="animate-spin" /> : null}
      {children}
    </button>
  ),
);

Button.displayName = "Button";
