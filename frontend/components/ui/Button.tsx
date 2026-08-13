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
    "grad-primary text-primary-fg font-semibold shadow-btn-primary hover:brightness-[1.06]",
  secondary:
    "border border-secondary/30 bg-secondary/15 text-secondary-soft hover:border-secondary/45 hover:bg-secondary/25",
  ghost:
    "border border-border bg-surface-input/50 text-content hover:border-primary/40 hover:bg-surface-raised/60 hover:text-primary-bright",
  danger: "border border-danger/30 bg-danger/5 text-danger hover:border-danger/45 hover:bg-danger/10",
  subtle: "border border-border/70 bg-surface-high/70 text-content hover:border-border-strong hover:bg-surface-raised",
};

const sizes: Record<Size, string> = {
  sm: "h-8 px-3 text-[13px] gap-1.5",
  md: "h-10 px-4 text-[13px] gap-2",
  lg: "h-[46px] px-5 text-sm gap-2",
  icon: "h-9 w-9",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "primary", size = "md", loading = false, className, children, disabled, ...props }, ref) => (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        "inline-flex select-none items-center justify-center rounded-md font-medium",
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
