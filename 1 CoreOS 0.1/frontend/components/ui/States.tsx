import type { ReactNode } from "react";
import { AlertTriangle, Inbox, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/Button";

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-12 text-content-muted">
      <Loader2 size={18} className="animate-spin" />
      <span className="text-sm">{label}</span>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  icon,
  action,
}: {
  title: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border px-6 py-12 text-center">
      <span className="mb-3 flex h-11 w-11 items-center justify-center rounded-lg border border-border bg-surface-input text-content-subtle">
        {icon ?? <Inbox size={20} />}
      </span>
      <p className="text-sm font-medium text-content">{title}</p>
      {description ? (
        <p className="mt-1 max-w-sm text-[13px] text-content-muted">{description}</p>
      ) : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-danger/30 bg-danger/5 px-6 py-10 text-center">
      <AlertTriangle size={20} className="mb-2 text-danger" />
      <p className="max-w-sm text-sm text-content">{message}</p>
      {onRetry ? (
        <Button variant="ghost" size="sm" className="mt-4" onClick={onRetry}>
          Try again
        </Button>
      ) : null}
    </div>
  );
}
