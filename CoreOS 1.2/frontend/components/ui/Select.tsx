import { forwardRef } from "react";
import type { SelectHTMLAttributes, ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/format";

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: ReactNode;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, id, className, children, ...props }, ref) => (
    <div className="space-y-1.5">
      {label ? (
        <label htmlFor={id} className="block text-[12px] font-medium uppercase tracking-wide text-content-muted">
          {label}
        </label>
      ) : null}
      <div className="relative">
        <select
          id={id}
          ref={ref}
          className={cn(
            "h-10 w-full appearance-none rounded-md border border-border bg-surface-input pl-3 pr-9 text-sm text-content",
            "focus:border-primary/70 focus:outline-none focus:ring-1 focus:ring-primary/30",
            "disabled:opacity-50",
            className,
          )}
          {...props}
        >
          {children}
        </select>
        <ChevronDown
          size={15}
          className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-content-subtle"
        />
      </div>
    </div>
  ),
);

Select.displayName = "Select";
