import { cn } from "@/lib/format";
import type { IntegrationStatusValue } from "@/types";

const colorByStatus: Record<IntegrationStatusValue, string> = {
  connected: "bg-success",
  configured: "bg-primary",
  not_configured: "bg-content-subtle",
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
  return (
    <span className={cn("relative inline-flex h-2.5 w-2.5", className)}>
      {pulse && status === "connected" ? (
        <span className="absolute inline-flex h-full w-full animate-pulse-soft rounded-full bg-success/60" />
      ) : null}
      <span className={cn("relative inline-flex h-2.5 w-2.5 rounded-full", colorByStatus[status])} />
    </span>
  );
}
