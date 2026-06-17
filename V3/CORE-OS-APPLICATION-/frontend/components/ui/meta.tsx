import { CheckCircle2, Circle, CircleDot } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/format";
import type { IntegrationStatusValue, TaskPriority, TaskStatus } from "@/types";

const CONFIG_STATUS: Record<string, { label: string; tone: "success" | "primary" | "neutral" | "danger" }> = {
  online: { label: "Online", tone: "success" },
  connected: { label: "Connected", tone: "success" },
  configured: { label: "Configured", tone: "primary" },
  not_configured: { label: "Not configured", tone: "neutral" },
  error: { label: "Error", tone: "danger" },
  disabled: { label: "Disabled", tone: "neutral" },
};

export function ConfigStatusBadge({ status }: { status: IntegrationStatusValue | string }) {
  const meta = CONFIG_STATUS[status] ?? CONFIG_STATUS.not_configured;
  return (
    <Badge tone={meta.tone} dot>
      {meta.label}
    </Badge>
  );
}

const priorityTone: Record<TaskPriority, "danger" | "warning" | "info" | "neutral"> = {
  URGENT: "danger",
  HIGH: "warning",
  NORMAL: "info",
  LOW: "neutral",
};

export function PriorityBadge({ priority }: { priority: TaskPriority }) {
  return <Badge tone={priorityTone[priority]}>{priority}</Badge>;
}

const statusMeta: Record<TaskStatus, { label: string; tone: string; icon: typeof Circle }> = {
  TODO: { label: "Todo", tone: "text-content-muted", icon: Circle },
  IN_PROGRESS: { label: "In Progress", tone: "text-info", icon: CircleDot },
  DONE: { label: "Done", tone: "text-success", icon: CheckCircle2 },
};

export function TaskStatusLabel({ status }: { status: TaskStatus }) {
  const meta = statusMeta[status];
  const Icon = meta.icon;
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-[13px] font-medium", meta.tone)}>
      <Icon size={14} />
      {meta.label}
    </span>
  );
}
