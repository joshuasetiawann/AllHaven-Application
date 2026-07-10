import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { StatusDot } from "@/components/ui/StatusDot";
import { ConfigStatusBadge } from "@/components/ui/meta";
import { cn } from "@/lib/format";
import type { Integration } from "@/types";

export function IntegrationStatusBanner({
  integration,
  label,
}: {
  integration?: Integration;
  label: string;
}) {
  const status = integration?.status ?? "not_configured";
  return (
    <Card
      gradient={status !== "not_configured"}
      className={cn(
        "mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between",
        status === "not_configured" &&
          "border-[rgb(var(--color-warning)/0.28)] bg-[linear-gradient(120deg,rgb(var(--color-warning)/0.07),rgb(var(--color-warning)/0.02))]",
      )}
      padding="md"
    >
      <div className="flex items-center gap-3">
        <span className="glass-tile flex h-9 w-9 shrink-0 items-center justify-center rounded-lg">
          <StatusDot status={status} pulse />
        </span>
        <div>
          <p className="text-sm font-semibold text-content">{label}</p>
          <p className="mt-0.5 font-mono text-[11px] tracking-[0.04em] text-content-muted">
            {integration?.detail ?? "Not configured"}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <ConfigStatusBadge status={status} />
        <Link
          href="/dashboard/settings"
          className="inline-flex items-center gap-1 text-[13px] font-medium text-primary transition-colors hover:text-primary-bright"
        >
          Configure in Settings <ArrowUpRight size={14} />
        </Link>
      </div>
    </Card>
  );
}
