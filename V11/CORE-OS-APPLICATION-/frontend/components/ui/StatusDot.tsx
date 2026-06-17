import { cn } from "@/lib/format";
import type { IntegrationStatusValue } from "@/types";

const colorByStatus: Record<string, string> = {
  online: "bg-success",
  connected: "bg-success",
  configured: "bg-primary",
  not_configured: "bg-content-subtle",
  unavailable: "bg-warning",
  disabled: "bg-content-subtle",
  error: "bg-danger",
};

export function StatusDot({
  status,
  pulse = false,
  className,
}: {
  status: IntegrationStatusValue | string;
  pulse?: boolean;
  className?: string;
}) {
  const color = colorByStatus[status] ?? "bg-content-subtle";
  const live = status === "online" || status === "connected" || status === "configured";
  return (
    <span className={cn("relative inline-flex h-2.5 w-2.5", className)}>
      {pulse && live ? (
        <span className={cn("absolute inline-flex h-full w-full animate-pulse-soft rounded-full opacity-60", color)} />
      ) : null}
      <span className={cn("relative inline-flex h-2.5 w-2.5 rounded-full", color)} />
    </span>
  );
}
