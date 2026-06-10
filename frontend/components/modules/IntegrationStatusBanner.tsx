import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { Card } from "@/components/ui/Card";
import { StatusDot } from "@/components/ui/StatusDot";
import { ConfigStatusBadge } from "@/components/ui/meta";
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
    <Card className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between" padding="md">
      <div className="flex items-center gap-3">
        <StatusDot status={status} pulse />
        <div>
          <p className="text-sm font-medium text-content">{label}</p>
          <p className="text-[12.5px] text-content-muted">{integration?.detail ?? "Not configured"}</p>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <ConfigStatusBadge status={status} />
        <Link
          href="/dashboard/settings"
          className="inline-flex items-center gap-1 text-[13px] text-primary hover:underline"
        >
          Configure in Settings <ArrowUpRight size={14} />
        </Link>
      </div>
    </Card>
  );
}
