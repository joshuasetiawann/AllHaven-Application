import { forwardRef } from "react";
import type { InputHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/format";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: ReactNode;
  hint?: ReactNode;
  leftIcon?: ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, hint, leftIcon, id, className, ...props }, ref) => (
    <div className="space-y-1.5">
      {label ? (
        <label htmlFor={id} className="block text-[11px] font-medium uppercase tracking-[0.08em] text-content-subtle">
          {label}
        </label>
      ) : null}
      <div className="relative">
        {leftIcon ? (
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-content-subtle">
            {leftIcon}
          </span>
        ) : null}
        <input
          id={id}
          ref={ref}
          className={cn(
            "h-10 w-full rounded-md border border-border bg-surface-input/80 text-sm text-content",
            "placeholder:text-content-faint",
            "focus:border-primary/50 focus:outline-none focus:ring-1 focus:ring-primary/30",
            "disabled:opacity-50",
            leftIcon ? "pl-9 pr-3" : "px-3",
            className,
          )}
          {...props}
        />
      </div>
      {hint ? <p className="text-[12px] text-content-subtle">{hint}</p> : null}
    </div>
  ),
);

Input.displayName = "Input";
