import type { ReactNode } from "react";
import { AlertTriangle, Inbox, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/format";

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-16 text-content-muted">
      <Loader2 size={18} className="animate-spin text-primary" />
      <span className="text-sm">{label}</span>
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton h-4 w-full", className)} />;
}

export function SkeletonCard() {
  return (
    <div className="panel space-y-3 p-5">
      <Skeleton className="h-8 w-8 rounded-lg" />
      <Skeleton className="h-6 w-1/2" />
      <Skeleton className="h-4 w-3/4" />
    </div>
  );
}

export function EmptyState({
  title,
  description,
  icon,
  action,
  className,
}: {
  title: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-xl border border-dashed border-border px-6 py-14 text-center",
        className,
      )}
    >
      <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-surface-input text-content-subtle">
        {icon ?? <Inbox size={20} />}
      </span>
      <p className="text-sm font-medium text-content">{title}</p>
      {description ? <p className="mt-1 max-w-sm text-[13px] text-content-muted">{description}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-danger/30 bg-danger/5 px-6 py-12 text-center">
      <AlertTriangle size={22} className="mb-2 text-danger" />
      <p className="max-w-sm text-sm text-content">{message}</p>
      {onRetry ? (
        <Button variant="ghost" size="sm" className="mt-4" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </div>
  );
}
