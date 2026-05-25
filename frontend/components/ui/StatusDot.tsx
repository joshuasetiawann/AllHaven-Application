import { cn } from "@/lib/format";
import type { IntegrationStatusValue } from "@/types";

const colorByStatus: Record<string, string> = {
  online: "bg-success",
  connected: "bg-success",
  configured: "bg-primary",
  not_configured: "bg-content-subtle",
  unavailable: "bg-content-subtle",
  disabled: "bg-content-subtle",
  error: "bg-danger",
};

export function StatusDot({
  status,
  pulse = false,
  className,
}: {
  status: IntegrationStatusValue;
  pulse?: boolean;
  className?: string;
}) {
  const color = colorByStatus[status] ?? "bg-content-subtle";
  const live = status === "online" || status === "connected" || status === "configured";
  return (
    <span className={cn("relative inline-flex h-2.5 w-2.5", className)}>
      {pulse && status === "connected" ? (
        <span className="absolute inline-flex h-full w-full animate-pulse-soft rounded-full bg-success/60" />
      ) : null}
      <span className={cn("relative inline-flex h-2.5 w-2.5 rounded-full", colorByStatus[status])} />
    </span>
  );
}
