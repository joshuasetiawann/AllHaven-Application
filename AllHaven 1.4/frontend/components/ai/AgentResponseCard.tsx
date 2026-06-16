"use client";

import Link from "next/link";
import { AlertTriangle, Bot, Globe, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { cn } from "@/lib/format";
import type { AgentResponseStatus } from "@/types";

export interface AgentCardData {
  provider_id: string;
  provider_name: string;
  status: AgentResponseStatus;
  content?: string | null;
  error_message?: string | null;
  latency_ms?: number | null;
  external?: boolean;
}

const STATUS_META: Record<
  AgentResponseStatus,
  { tone: "success" | "danger" | "warning" | "neutral" | "primary"; label: string }
> = {
  queued: { tone: "neutral", label: "Queued" },
  running: { tone: "primary", label: "Running" },
  completed: { tone: "success", label: "Completed" },
  error: { tone: "danger", label: "Error" },
  not_configured: { tone: "neutral", label: "Not configured" },
  disabled: { tone: "neutral", label: "Disabled" },
  blocked: { tone: "warning", label: "Blocked" },
};

export function AgentResponseCard({ data }: { data: AgentCardData }) {
  const meta = STATUS_META[data.status] ?? STATUS_META.error;
  const busy = data.status === "queued" || data.status === "running";
  const needsSetup = data.status === "not_configured" || data.status === "disabled" || data.status === "blocked";

  return (
    <div className="flex min-w-0 flex-col rounded-xl border border-border bg-surface-input">
      <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
            <Bot size={13} />
          </span>
          <span className="truncate text-[13px] font-medium text-content">{data.provider_name}</span>
          {data.external ? <Globe size={12} className="shrink-0 text-warning" aria-label="External" /> : null}
        </div>
        <Badge tone={meta.tone} className="shrink-0">
          {busy ? <Loader2 size={11} className="mr-1 inline animate-spin" /> : null}
          {meta.label}
        </Badge>
      </div>

      <div className="min-w-0 flex-1 px-3 py-2.5 text-[13px] leading-relaxed">
        {data.status === "completed" ? (
          <p className="whitespace-pre-wrap break-words text-content-muted">{data.content}</p>
        ) : busy ? (
          <p className="text-content-subtle">Waiting for a response…</p>
        ) : needsSetup ? (
          <div className="flex items-start gap-1.5 text-content-muted">
            <AlertTriangle size={13} className="mt-0.5 shrink-0 text-warning" />
            <span className="break-words">
              {data.error_message}{" "}
              <Link href="/dashboard/settings" className="text-primary hover:underline">
                Open Settings →
              </Link>
            </span>
          </div>
        ) : (
          <p className={cn("break-words text-danger")}>{data.error_message || "The agent failed."}</p>
        )}
      </div>

      {data.latency_ms != null && data.status === "completed" ? (
        <p className="px-3 pb-2 text-[10.5px] text-content-subtle">{data.latency_ms} ms</p>
      ) : null}
    </div>
  );
}
