import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/format";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  hover?: boolean;
  gradient?: boolean;
  padding?: "none" | "sm" | "md" | "lg";
}

const paddings = { none: "", sm: "p-[18px]", md: "p-5", lg: "p-6" };

export function Card({ hover, gradient, padding = "md", className, ...props }: CardProps) {
  return (
    <div
      className={cn(
        gradient ? "panel-gradient" : "panel",
        paddings[padding],
        hover && "panel-hover",
        className,
      )}
      {...props}
    />
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
    <div className={cn("mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between", className)}>
      <div className="flex min-w-0 items-center gap-2.5">
        {icon ? (
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-primary/20 bg-primary/10 text-primary-bright">
            {icon}
          </span>
        ) : null}
        <div className="min-w-0">
          <h3 className="truncate text-[15px] font-semibold text-content">{title}</h3>
          {subtitle ? <p className="mt-0.5 text-[12.5px] text-content-muted">{subtitle}</p> : null}
        </div>
      </div>
      {action ? <div className="shrink-0 sm:ml-auto">{action}</div> : null}
    </div>
  );
}
