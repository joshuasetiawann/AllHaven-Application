import { forwardRef } from "react";
import type { TextareaHTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/format";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: ReactNode;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, id, className, ...props }, ref) => (
    <div className="space-y-1.5">
      {label ? (
        <label htmlFor={id} className="block text-[13px] font-medium text-content-muted">
          {label}
        </label>
      ) : null}
      <textarea
        id={id}
        ref={ref}
        className={cn(
          "w-full rounded-md border border-border bg-surface-input px-3 py-2 text-sm text-content",
          "placeholder:text-content-subtle min-h-[96px] resize-y",
          "focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/40",
          "disabled:opacity-50",
          className,
        )}
        {...props}
      />
    </div>
  ),
);

Textarea.displayName = "Textarea";
