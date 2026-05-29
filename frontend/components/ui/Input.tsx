import { forwardRef } from "react";
import type { InputHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/format";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, id, className, ...props }, ref) => (
    <div className="space-y-1.5">
      {label ? (
        <label htmlFor={id} className="block text-[13px] font-medium text-content-muted">
          {label}
        </label>
      ) : null}
      <input
        id={id}
        ref={ref}
        className={cn(
          "h-10 w-full rounded-md border border-border bg-surface-input px-3 text-sm text-content",
          "placeholder:text-content-subtle font-mono",
          "focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40",
          "disabled:opacity-50",
          className,
        )}
        {...props}
      />
    </div>
  ),
);

Input.displayName = "Input";
