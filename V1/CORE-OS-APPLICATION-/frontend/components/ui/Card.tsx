import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/format";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  hover?: boolean;
}

export function Card({ hover = false, className, ...props }: CardProps) {
  return (
    <div className={cn("panel p-5", hover && "panel-hover", className)} {...props} />
  );
}

interface CardHeaderProps {
  title: ReactNode;
  subtitle?: ReactNode;
  icon?: ReactNode;
  action?: ReactNode;
  className?: string;
}

export function CardHeader({ title, subtitle, icon, action, className }: CardHeaderProps) {
  return (
    <div className={cn("mb-4 flex items-start justify-between gap-3", className)}>
      <div className="flex items-center gap-3">
        {icon ? (
          <span className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-surface-input text-primary">
            {icon}
          </span>
        ) : null}
        <div>
          <h3 className="text-[15px] font-semibold text-content">{title}</h3>
          {subtitle ? (
            <p className="mt-0.5 text-[13px] text-content-muted">{subtitle}</p>
          ) : null}
        </div>
      </div>
      {action}
    </div>
  );
}
