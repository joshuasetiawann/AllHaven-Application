import { CheckCircle2, Circle, CircleDot } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/format";
import type { TaskPriority, TaskStatus } from "@/types";

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
